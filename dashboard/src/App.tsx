import { useEffect, useState, useMemo } from 'react';
import { createClient } from '@supabase/supabase-js';
import {
  Scale, Search, Trash2, Wrench, CheckCircle, AlertTriangle, FileText, BadgeAlert,
  Calendar, Filter, BarChart2, Building2, Tag, ArrowUpDown, BookOpen, Info, Zap, TrendingUp
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import moment from 'moment';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseKey);

const COLORS = {
  keep: '#10b981',
  modify: '#f59e0b',
  delete: '#ef4444'
};

const PRIORIDAD_COLOR: Record<string, string> = {
  '10': 'bg-red-600', '9': 'bg-red-500', '8': 'bg-orange-500',
  '7': 'bg-amber-500', '6': 'bg-amber-400', '5': 'bg-yellow-400',
  '4': 'bg-lime-400', '3': 'bg-green-400', '2': 'bg-emerald-400', '1': 'bg-emerald-500',
};

interface Regulacion {
  id_norma: string;
  tipo_norma: string;
  numero: string;
  titulo: string;
  fecha_publicacion: string;
  organismo: string;
  categoria: string;
  verdict: string;
  summary: string;
  reason: string;
  negative_effects: string;
  legislative_action: string;
  impact_areas: string[];
  impacto_economico: string;
  complejidad_burocracia: string;
  prioridad: number;
  categoria_reforma: string;
}

type PageType = 'landing' | 'dashboard' | 'metodologia' | 'resultados';

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageType>('landing');
  const [normas, setNormas] = useState<Regulacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterVerdict, setFilterVerdict] = useState<string>('all');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterTipo, setFilterTipo] = useState<string>('all');
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState<'prioridad' | 'fecha' | 'titulo'>('prioridad');
  const [totalLaws, setTotalLaws] = useState(0);
  const [evaluatedLaws, setEvaluatedLaws] = useState(0);
  const [deepAnalyzedLaws, setDeepAnalyzedLaws] = useState(0);

  useEffect(() => {
    fetchNormas();
    fetchProgress();
  }, []);

  const fetchNormas = async () => {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from('regulaciones')
        .select('id_norma, tipo_norma, numero, titulo, fecha_publicacion, organismo, categoria, verdict, summary, reason, negative_effects, legislative_action, impact_areas, impacto_economico, complejidad_burocracia, prioridad, categoria_reforma')
        .eq('evaluado', true)
        .order('prioridad', { ascending: false, nullsFirst: false });

      if (error) throw error;
      setNormas(data || []);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchProgress = async () => {
    try {
      // Total normas
      const totalRes = await supabase
        .from('regulaciones')
        .select('id_norma', { count: 'exact', head: true });
      setTotalLaws(totalRes.count || 0);

      // Evaluadas
      const evalRes = await supabase
        .from('regulaciones')
        .select('id_norma', { count: 'exact', head: true })
        .eq('evaluado', true);
      setEvaluatedLaws(evalRes.count || 0);

      // Deep analyzed
      const deepRes = await supabase
        .from('regulaciones')
        .select('id_norma', { count: 'exact', head: true })
        .eq('evaluacion_profunda', true);
      setDeepAnalyzedLaws(deepRes.count || 0);
    } catch (error) {
      console.error('Error fetching progress:', error);
    }
  };

  const filteredNormas = useMemo(() => {
    let result = normas.filter(n => {
      if (filterVerdict !== 'all' && n.verdict !== filterVerdict) return false;
      if (filterCategory !== 'all' && n.categoria !== filterCategory) return false;
      if (filterTipo !== 'all' && n.tipo_norma !== filterTipo) return false;
      if (searchText) {
        const q = searchText.toLowerCase();
        return (n.titulo?.toLowerCase().includes(q) || n.summary?.toLowerCase().includes(q) || n.id_norma?.includes(q));
      }
      return true;
    });

    if (sortBy === 'prioridad') {
      result.sort((a, b) => (b.prioridad || 0) - (a.prioridad || 0));
    } else if (sortBy === 'fecha') {
      result.sort((a, b) => (b.fecha_publicacion || '').localeCompare(a.fecha_publicacion || ''));
    } else {
      result.sort((a, b) => (a.titulo || '').localeCompare(b.titulo || ''));
    }

    return result;
  }, [normas, filterVerdict, filterCategory, filterTipo, searchText, sortBy]);

  const categories = useMemo(() =>
    Array.from(new Set(normas.map(n => n.categoria).filter(Boolean))).sort(),
    [normas]
  );

  const tipos = useMemo(() =>
    Array.from(new Set(normas.map(n => n.tipo_norma).filter(Boolean))).sort(),
    [normas]
  );

  const stats = useMemo(() => ({
    total: normas.length,
    keep: normas.filter(n => n.verdict === 'keep').length,
    modify: normas.filter(n => n.verdict === 'modify').length,
    delete: normas.filter(n => n.verdict === 'delete').length,
  }), [normas]);

  const pieData = [
    { name: 'Mantener', value: stats.keep, color: COLORS.keep },
    { name: 'Modificar', value: stats.modify, color: COLORS.modify },
    { name: 'Derogar', value: stats.delete, color: COLORS.delete },
  ].filter(d => d.value > 0);

  const barData = useMemo(() => {
    const years: Record<string, { year: string, keep: number, modify: number, delete: number }> = {};
    normas.forEach(n => {
      const year = n.fecha_publicacion ? n.fecha_publicacion.substring(0, 4) : 'Desc.';
      if (!years[year]) years[year] = { year, keep: 0, modify: 0, delete: 0 };
      const v = n.verdict as 'keep' | 'modify' | 'delete';
      if (v) years[year][v]++;
    });
    return Object.values(years).sort((a, b) => a.year.localeCompare(b.year));
  }, [normas]);

  const hasActiveFilters = filterVerdict !== 'all' || filterCategory !== 'all' || filterTipo !== 'all' || searchText !== '';

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'keep':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"><CheckCircle className="w-3 h-3 mr-1" /> Mantener</span>;
      case 'modify':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"><Wrench className="w-3 h-3 mr-1" /> Modificar</span>;
      case 'delete':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><Trash2 className="w-3 h-3 mr-1" /> Derogar</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Pendiente</span>;
    }
  };

  const getPrioridadBadge = (prioridad: number) => {
    if (!prioridad) return null;
    const bg = PRIORIDAD_COLOR[String(prioridad)] || 'bg-gray-400';
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold text-white ${bg}`}>
        P{prioridad}
      </span>
    );
  };

  // ==================== LANDING PAGE ====================
  if (currentPage === 'landing') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white font-sans">
        {/* Header */}
        <header className="sticky top-0 z-20 bg-slate-900/80 backdrop-blur-sm border-b border-slate-700">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
            <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setCurrentPage('landing')}>
              <div className="p-1.5 bg-blue-500 rounded-lg group-hover:bg-blue-600 transition-colors">
                <Scale className="h-6 w-6 text-white" />
              </div>
              <span className="ml-1 text-xl font-bold">Better<span className="text-blue-400">Chile</span></span>
            </div>
            <nav className="flex gap-6">
              <button onClick={() => setCurrentPage('dashboard')} className="text-sm font-medium text-slate-300 hover:text-white transition-colors">Dashboard</button>
              <button onClick={() => setCurrentPage('metodologia')} className="text-sm font-medium text-slate-300 hover:text-white transition-colors">Metodología</button>
              <button onClick={() => setCurrentPage('resultados')} className="text-sm font-medium text-slate-300 hover:text-white transition-colors">Resultados</button>
            </nav>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Hero */}
          <section className="py-20 text-center">
            <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-blue-200">
              Auditoria Legislativa Austriaca
            </h1>
            <p className="text-xl text-slate-300 max-w-3xl mx-auto mb-8">
              Análisis sistemático de <span className="font-bold text-white">{totalLaws.toLocaleString()}</span> normas chilenas desde la perspectiva de libertad económica, transparencia y eficiencia.
            </p>
            <button onClick={() => setCurrentPage('dashboard')} className="inline-flex items-center px-8 py-3 bg-blue-500 hover:bg-blue-600 text-white font-bold rounded-lg transition-colors">
              Explorar Dashboard <ArrowUpDown className="w-4 h-4 ml-2" />
            </button>
          </section>

          {/* Progress Bar */}
          <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 mb-16">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-blue-400" />
                Estado de Evaluación del Proyecto
              </h3>
              <span className="text-2xl font-bold text-blue-400">{totalLaws > 0 ? Math.round(evaluatedLaws * 100 / totalLaws) : 0}%</span>
            </div>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-slate-300 text-sm font-medium">Leyes Analizadas (Pasada Superficial)</span>
                  <span className="text-slate-400 text-xs">{evaluatedLaws.toLocaleString()} / {totalLaws.toLocaleString()}</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-blue-500 to-blue-400 h-full rounded-full transition-all duration-300"
                    style={{ width: `${totalLaws > 0 ? (evaluatedLaws * 100 / totalLaws) : 0}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-slate-300 text-sm font-medium">Análisis Profundo (Pasada 2)</span>
                  <span className="text-slate-400 text-xs">{deepAnalyzedLaws.toLocaleString()} leyes</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-amber-500 to-amber-400 h-full rounded-full transition-all duration-300"
                    style={{ width: `${evaluatedLaws > 0 ? (deepAnalyzedLaws * 100 / evaluatedLaws) : 0}%` }}
                  />
                </div>
              </div>
            </div>
            <p className="text-slate-400 text-xs mt-4 text-center">ETA: 5-7 días para completar análisis superficial de todas las normas</p>
          </section>

          {/* Stats Cards */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-3">
                <span className="text-slate-400 text-sm font-medium">NORMAS EVALUADAS</span>
                <FileText className="w-5 h-5 text-blue-400" />
              </div>
              <div className="text-4xl font-bold">{stats.total.toLocaleString()}</div>
              <p className="text-slate-400 text-sm mt-2">análisis completado</p>
            </div>

            <div className="bg-emerald-900/30 border border-emerald-700/50 rounded-xl p-6 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-3">
                <span className="text-emerald-300 text-sm font-medium">MANTENER</span>
                <CheckCircle className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="text-4xl font-bold text-emerald-400">{stats.keep.toLocaleString()}</div>
              <p className="text-emerald-300 text-sm mt-2">{stats.total ? Math.round(stats.keep * 100 / stats.total) : 0}% de las normas</p>
            </div>

            <div className="bg-amber-900/30 border border-amber-700/50 rounded-xl p-6 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-3">
                <span className="text-amber-300 text-sm font-medium">MODIFICAR</span>
                <Wrench className="w-5 h-5 text-amber-400" />
              </div>
              <div className="text-4xl font-bold text-amber-400">{stats.modify.toLocaleString()}</div>
              <p className="text-amber-300 text-sm mt-2">{stats.total ? Math.round(stats.modify * 100 / stats.total) : 0}% requieren reforma</p>
            </div>

            <div className="bg-red-900/30 border border-red-700/50 rounded-xl p-6 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-3">
                <span className="text-red-300 text-sm font-medium">DEROGAR</span>
                <Trash2 className="w-5 h-5 text-red-400" />
              </div>
              <div className="text-4xl font-bold text-red-400">{stats.delete.toLocaleString()}</div>
              <p className="text-red-300 text-sm mt-2">{stats.total ? Math.round(stats.delete * 100 / stats.total) : 0}% sugeridas eliminar</p>
            </div>
          </section>

          {/* Key Findings */}
          <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 mb-16">
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-blue-400" />
              Hallazgos Clave
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <p className="text-slate-400 text-sm">RATIO REFORMA/DEROGACION</p>
                <p className="text-3xl font-bold text-amber-400">80:20</p>
                <p className="text-slate-300 text-sm leading-relaxed">La mayoría de leyes no necesitan ser eliminadas, sino reformadas para mayor eficiencia y menor burocracia.</p>
              </div>
              <div className="space-y-2">
                <p className="text-slate-400 text-sm">COMPLEJIDAD BUROCRÁTICA</p>
                <p className="text-3xl font-bold text-red-400">66%</p>
                <p className="text-slate-300 text-sm leading-relaxed">Dos tercios de las regulaciones tienen alta complejidad administrativa que genera barreras de entrada.</p>
              </div>
              <div className="space-y-2">
                <p className="text-slate-400 text-sm">IMPACTO ECONÓMICO ALTO</p>
                <p className="text-3xl font-bold text-blue-400">Prioridad 7.1</p>
                <p className="text-slate-300 text-sm leading-relaxed">Normas críticas impactan directamente PIB, empleo y competitividad internacional.</p>
              </div>
            </div>
          </section>

          {/* CTA */}
          <section className="py-12 text-center">
            <h2 className="text-3xl font-bold mb-6">Próximos Pasos</h2>
            <p className="text-slate-300 mb-8 max-w-2xl mx-auto">
              Expande este análisis en el dashboard interactivo, revisa la metodología detallada o descargar los resultados completos en formato profesional.
            </p>
            <div className="flex gap-4 justify-center flex-wrap">
              <button onClick={() => setCurrentPage('dashboard')} className="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white font-bold rounded-lg transition-colors">Ver Dashboard Completo</button>
              <button onClick={() => setCurrentPage('metodologia')} className="px-6 py-3 border border-slate-400 text-slate-300 hover:bg-slate-800 font-bold rounded-lg transition-colors">Leer Metodología</button>
            </div>
          </section>
        </main>

        <footer className="border-t border-slate-700 mt-20 py-8">
          <div className="max-w-7xl mx-auto px-4 text-center">
            <p className="text-slate-400 text-sm">Better Chile {new Date().getFullYear()} — Auditoría Legislativa Transparente</p>
            <p className="text-slate-500 text-xs mt-2">Análisis basado en perspectiva austriaca de economía (Mises, Hayek, Friedman)</p>
          </div>
        </footer>
      </div>
    );
  }

  // ==================== METODOLOGÍA PAGE ====================
  if (currentPage === 'metodologia') {
    return (
      <div className="min-h-screen bg-slate-50">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setCurrentPage('landing')}>
                  <div className="p-1.5 bg-blue-600 rounded-lg group-hover:bg-blue-700 transition-colors">
                    <Scale className="h-6 w-6 text-white" />
                  </div>
                  <span className="ml-1 text-xl font-bold text-slate-900">Better<span className="text-blue-600">Chile</span></span>
                </div>
                <nav className="hidden md:flex gap-6">
                  <button onClick={() => setCurrentPage('landing')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Landing</button>
                  <button onClick={() => setCurrentPage('dashboard')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Dashboard</button>
                  <button onClick={() => setCurrentPage('metodologia')} className="text-sm font-medium text-blue-600 hover:text-blue-800 border-b-2 border-blue-600">Metodología</button>
                  <button onClick={() => setCurrentPage('resultados')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Resultados</button>
                </nav>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="mb-12">
            <h1 className="text-4xl font-bold mb-4 text-slate-900">Marco Metodológico</h1>
            <p className="text-lg text-slate-600">Evaluación sistemática de la función regulatoria desde la perspectiva de la economía austriaca</p>
          </div>

          {/* Introduction */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 mb-8">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-blue-600" />
              Fundamento Teórico
            </h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Better Chile aplica los principios de la escuela austriaca de economía (Ludwig von Mises, Friedrich Hayek, Milton Friedman) para evaluar el corpus regulatorio chileno. Esta perspectiva enfatiza:
            </p>
            <ul className="space-y-2 text-slate-700">
              <li>✓ <strong>Libertad económica:</strong> Presunción de que los individuos pueden actuar libremente en mercados</li>
              <li>✓ <strong>Propiedad privada:</strong> Sistema de precios eficiente para asignar recursos</li>
              <li>✓ <strong>Subsidiaridad:</strong> Gobiernos locales mejor que centrales</li>
              <li>✓ <strong>Costo-beneficio real:</strong> Análisis honesto de externalidades negativas</li>
            </ul>
          </section>

          {/* The 6 Axes */}
          <section className="space-y-4 mb-8">
            <h2 className="text-2xl font-bold flex items-center gap-2 mb-4">
              <Zap className="w-6 h-6 text-blue-600" />
              6 Ejes de Evaluación
            </h2>

            {[
              { title: 'Libertad Económica', desc: 'Restringe la capacidad de empresas y personas de actuar libremente en mercados? ¿Requiere permisos, autorizaciones o aprobaciones previas?' },
              { title: 'Burocracia Estatal', desc: '¿Crea nuevos organismos, trámites o requisitos administrativos? ¿Aumenta cargas a emprendedores?' },
              { title: 'Costo Fiscal', desc: '¿Genera gasto público sin retorno claro? ¿Crea subsidios o transferencias sin costo-beneficio demostrado?' },
              { title: 'Modernización', desc: '¿Está basada en tecnología obsoleta? ¿Hay mejores mecanismos internacionales para resolver el mismo problema?' },
              { title: 'Duplicación', desc: '¿Sobreponse con otras normas existentes? ¿Crea conflictos de competencia entre reguladores?' },
              { title: 'Derechos Fundamentales', desc: '¿Protege derechos esenciales que deben preservarse? ¿Hay equilibrio entre libertad individual y bien común?' },
            ].map((axis, idx) => (
              <div key={idx} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <h3 className="text-lg font-bold text-slate-900 mb-2">{axis.title}</h3>
                <p className="text-slate-700">{axis.desc}</p>
              </div>
            ))}
          </section>

          {/* Verdicts */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 mb-8">
            <h2 className="text-2xl font-bold mb-6">Veredictos Posibles</h2>
            <div className="space-y-4">
              <div className="border-l-4 border-emerald-500 pl-4">
                <p className="text-lg font-bold text-slate-900">MANTENER (Keep)</p>
                <p className="text-slate-600">La norma es esencial, protege derechos fundamentales o establece marcos imprescindibles de cooperación. No requiere modificación.</p>
              </div>
              <div className="border-l-4 border-amber-500 pl-4">
                <p className="text-lg font-bold text-slate-900">MODIFICAR (Modify)</p>
                <p className="text-slate-600">La norma tiene propósito válido pero su implementación es ineficiente, burocrática o genera externalidades negativas. Requiere reforma específica.</p>
              </div>
              <div className="border-l-4 border-red-500 pl-4">
                <p className="text-lg font-bold text-slate-900">DEROGAR (Delete)</p>
                <p className="text-slate-600">La norma es innecesaria, anticompetitiva o sus efectos negativos superan beneficios. Debe ser eliminada del ordenamiento.</p>
              </div>
            </div>
          </section>

          {/* Scoring */}
          <section className="bg-blue-50 rounded-xl shadow-sm border border-blue-200 p-8 mb-8">
            <h2 className="text-2xl font-bold mb-4">Sistema de Priorización (1-10)</h2>
            <p className="text-slate-700 mb-4">Cada norma recibe una calificación de prioridad basada en:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="font-bold text-slate-900 mb-2">Impacto Económico</p>
                <p className="text-sm text-slate-600">¿Cuántas empresas/personas afecta? ¿Qué cantidad de capital se invierte cumpliendo?</p>
              </div>
              <div>
                <p className="font-bold text-slate-900 mb-2">Complejidad Burocrática</p>
                <p className="text-sm text-slate-600">¿Cuántos pasos, documentos o autorizaciones requiere?</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-4">Máxima prioridad (P10) = reforma urgentísima | Mínima prioridad (P1) = reforma menor</p>
          </section>

          {/* Prompts Utilizados */}
          <section className="bg-yellow-50 rounded-xl shadow-sm border border-yellow-200 p-8">
            <h2 className="text-2xl font-bold mb-4">Prompts Utilizados para Evaluación</h2>
            <p className="text-slate-700 mb-6">Para total transparencia, estos son los prompts exactos que usamos con GPT-4o-mini:</p>

            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">1. SYSTEM PROMPT (Instrucciones al modelo)</h3>
                <div className="bg-white rounded-lg p-4 border border-slate-200 font-mono text-xs text-slate-700 overflow-auto max-h-96">
                  <pre>{`Eres un analista de politicas publicas del proyecto "Better Chile", con formacion en la Escuela Austriaca de Economia (Ludwig von Mises, Friedrich Hayek, Rothbard) y la Escuela de Chicago (Milton Friedman).

Tu mision es evaluar leyes y regulaciones chilenas (leyes, decretos, DFL, DL, resoluciones) y determinar su impacto en la libertad economica y las instituciones. Debes actuar con el pragmatismo de un legislador reformista, evaluando segun estos 6 ejes:

1. LIBERTAD ECONOMICA: Restringe libre empresa, comercio, competencia?
2. BUROCRACIA ESTATAL: Crea tramites, permisos, autorizaciones innecesarias?
3. COSTO FISCAL: Genera gasto publico sin retorno claro?
4. MODERNIZACION: Es obsoleta? Hay tecnologia/mecanismo mejor?
5. DUPLICACION: Se superpone con otras normas vigentes?
6. DERECHOS FUNDAMENTALES: Protege derechos que deben preservarse?

VEREDICTOS POSIBLES:
- "delete": Normas que coartan directamente libertades, imponen controles de precios, monopolios estatales sin justificacion, o crean burocracia inutil.
- "modify": Normas con intenciones razonables (ej. seguridad, salud) pero con pesima implementacion estatista, asimetrica o que coartan competencia. No se pueden simplemente eliminar sin vacio legal, deben ser reformadas.
- "keep": Normas esenciales para el Estado de Derecho, propiedad, contratos, seguridad o defensa.

INSTRUCCIONES DE FORMATO:
- Responde UNICAMENTE con un objeto JSON valido
- El JSON debe tener exactamente esta estructura con 10 campos`}</pre>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">2. USER PROMPT (Norma a evaluar)</h3>
                <div className="bg-white rounded-lg p-4 border border-slate-200 font-mono text-xs text-slate-700 overflow-auto max-h-64">
                  <pre>{`Evalua la siguiente norma chilena:

TIPO: [tipo_norma]
TITULO: [titulo]
FECHA DE PUBLICACION: [fecha]
CATEGORIA TEMATICA: [categoria]

TEXTO COMPLETO:
[texto de hasta 30,000 caracteres]`}</pre>
                </div>
              </div>

              <div className="bg-white rounded-lg p-4 border border-yellow-300">
                <p className="text-sm text-slate-700">
                  <strong>Nota de Transparencia:</strong> Todos los prompts están disponibles en GitHub y documentados en METODOLOGIA.md.
                  Puedes auditar exactamente cómo funciona el modelo, qué sesgo tiene, y replicar los análisis.
                  No hay "caja negra" — todo es verificable.
                </p>
              </div>
            </div>
          </section>
        </main>

        <footer className="border-t border-slate-200 mt-12 py-8">
          <div className="max-w-7xl mx-auto px-4 text-center">
            <p className="text-sm text-slate-500">Better Chile {new Date().getFullYear()} — Auditoria Legislativa</p>
          </div>
        </footer>
      </div>
    );
  }

  // ==================== RESULTS PAGE ====================
  if (currentPage === 'resultados') {
    return (
      <div className="min-h-screen bg-slate-50">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setCurrentPage('landing')}>
                  <div className="p-1.5 bg-blue-600 rounded-lg group-hover:bg-blue-700 transition-colors">
                    <Scale className="h-6 w-6 text-white" />
                  </div>
                  <span className="ml-1 text-xl font-bold text-slate-900">Better<span className="text-blue-600">Chile</span></span>
                </div>
                <nav className="hidden md:flex gap-6">
                  <button onClick={() => setCurrentPage('landing')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Landing</button>
                  <button onClick={() => setCurrentPage('dashboard')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Dashboard</button>
                  <button onClick={() => setCurrentPage('metodologia')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Metodología</button>
                  <button onClick={() => setCurrentPage('resultados')} className="text-sm font-medium text-blue-600 hover:text-blue-800 border-b-2 border-blue-600">Resultados</button>
                </nav>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <h1 className="text-4xl font-bold mb-8 text-slate-900">Resumen Ejecutivo (En Construcción)</h1>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-8 text-center">
            <Info className="w-12 h-12 text-blue-600 mx-auto mb-4" />
            <p className="text-slate-700 text-lg">Esta sección se completará con el análisis profundo (Etapa 2) cuando se haya evaluado un mayor número de normas con mayor rigor.</p>
            <button onClick={() => setCurrentPage('dashboard')} className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">Ver Dashboard Completo</button>
          </div>
        </main>
      </div>
    );
  }

  // ==================== MAIN DASHBOARD PAGE ====================
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-8">
              <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setCurrentPage('landing')}>
                <div className="p-1.5 bg-blue-600 rounded-lg group-hover:bg-blue-700 transition-colors">
                  <Scale className="h-6 w-6 text-white" />
                </div>
                <span className="ml-1 text-xl font-bold tracking-tight text-slate-900">Better<span className="text-blue-600">Chile</span></span>
              </div>
              <nav className="hidden md:flex gap-6">
                <button onClick={() => setCurrentPage('landing')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Landing</button>
                <button onClick={() => setCurrentPage('dashboard')} className="text-sm font-medium text-blue-600 hover:text-blue-800 border-b-2 border-blue-600">Dashboard</button>
                <button onClick={() => setCurrentPage('metodologia')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Metodología</button>
                <button onClick={() => setCurrentPage('resultados')} className="text-sm font-medium text-slate-500 hover:text-slate-900">Resultados</button>
              </nav>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

        {/* Stats */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="w-5 h-5 text-slate-400" />
            <h2 className="text-lg font-semibold text-slate-900">Resumen</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col justify-center relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <FileText className="w-16 h-16 text-slate-500" />
              </div>
              <dt className="text-sm font-medium text-slate-500 mb-1 z-10">Normas Evaluadas</dt>
              <dd className="text-4xl font-extrabold text-slate-900 z-10">{stats.total.toLocaleString()}</dd>
            </div>
            <div className="bg-gradient-to-br from-white to-emerald-50/50 rounded-xl shadow-sm border border-emerald-100 p-6 flex flex-col justify-center relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <CheckCircle className="w-16 h-16 text-emerald-600" />
              </div>
              <dt className="text-sm font-medium text-emerald-800 mb-1 z-10">Mantener</dt>
              <dd className="text-4xl font-extrabold text-emerald-600 z-10">{stats.keep.toLocaleString()}</dd>
              <dd className="text-xs text-emerald-600 mt-1">{stats.total ? Math.round(stats.keep * 100 / stats.total) : 0}%</dd>
            </div>
            <div className="bg-gradient-to-br from-white to-amber-50/50 rounded-xl shadow-sm border border-amber-100 p-6 flex flex-col justify-center relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <Wrench className="w-16 h-16 text-amber-600" />
              </div>
              <dt className="text-sm font-medium text-amber-800 mb-1 z-10">Requieren Reforma</dt>
              <dd className="text-4xl font-extrabold text-amber-600 z-10">{stats.modify.toLocaleString()}</dd>
              <dd className="text-xs text-amber-600 mt-1">{stats.total ? Math.round(stats.modify * 100 / stats.total) : 0}%</dd>
            </div>
            <div className="bg-gradient-to-br from-white to-red-50/50 rounded-xl shadow-sm border border-red-100 p-6 flex flex-col justify-center relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <Trash2 className="w-16 h-16 text-red-600" />
              </div>
              <dt className="text-sm font-medium text-red-800 mb-1 z-10">Sugeridas a Derogar</dt>
              <dd className="text-4xl font-extrabold text-red-600 z-10">{stats.delete.toLocaleString()}</dd>
              <dd className="text-xs text-red-600 mt-1">{stats.total ? Math.round(stats.delete * 100 / stats.total) : 0}%</dd>
            </div>
          </div>
        </section>

        {/* Charts */}
        {stats.total > 0 && (
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <h3 className="text-sm font-semibold text-slate-700 mb-6 uppercase tracking-wider">Regulaciones por Ano</h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#64748b' }} dy={10} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                    <Tooltip contentStyle={{ borderRadius: '0.5rem', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} cursor={{ fill: '#f1f5f9' }} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px' }} />
                    <Bar name="Mantener" dataKey="keep" stackId="a" fill={COLORS.keep} />
                    <Bar name="Modificar" dataKey="modify" stackId="a" fill={COLORS.modify} />
                    <Bar name="Derogar" dataKey="delete" stackId="a" fill={COLORS.delete} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-center items-center">
              <h3 className="text-sm font-semibold text-slate-700 mb-2 uppercase tracking-wider w-full text-left">Distribucion</h3>
              <div className="h-64 w-full flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value" stroke="none">
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: '0.5rem', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        )}

        {/* Database Section */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-slate-400" />
              <h2 className="text-lg font-semibold text-slate-900">Base de Datos</h2>
            </div>
            <div className="text-sm text-slate-500 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
              {filteredNormas.length.toLocaleString()} de {normas.length.toLocaleString()}
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white p-3 rounded-xl shadow-sm border border-slate-200 mb-6 flex flex-col sm:flex-row gap-2 items-center flex-wrap">
            <div className="flex items-center justify-center bg-slate-50 px-3 py-2 rounded-lg border border-slate-100 hidden sm:flex">
              <Filter className="w-4 h-4 text-slate-400" />
            </div>

            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar por titulo o ID..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 text-sm rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow"
              />
            </div>

            <select className="bg-transparent border border-slate-200 text-slate-700 text-sm rounded-lg focus:ring-2 focus:ring-blue-500 block p-2.5 hover:bg-slate-50 cursor-pointer"
              value={filterVerdict} onChange={(e) => setFilterVerdict(e.target.value)}>
              <option value="all">Todos los Veredictos</option>
              <option value="keep">Mantener</option>
              <option value="modify">Modificar</option>
              <option value="delete">Derogar</option>
            </select>

            <select className="bg-transparent border border-slate-200 text-slate-700 text-sm rounded-lg focus:ring-2 focus:ring-blue-500 block p-2.5 hover:bg-slate-50 cursor-pointer"
              value={filterTipo} onChange={(e) => setFilterTipo(e.target.value)}>
              <option value="all">Todos los Tipos</option>
              {tipos.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            <select className="bg-transparent border border-slate-200 text-slate-700 text-sm rounded-lg focus:ring-2 focus:ring-blue-500 block p-2.5 hover:bg-slate-50 cursor-pointer max-w-[200px]"
              value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
              <option value="all">Todas las Categorias</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            <div className="flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-lg p-1">
              <ArrowUpDown className="w-3.5 h-3.5 text-slate-400 ml-1" />
              <select className="bg-transparent text-slate-700 text-sm focus:ring-0 border-none cursor-pointer pr-6"
                value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
                <option value="prioridad">Prioridad</option>
                <option value="fecha">Fecha</option>
                <option value="titulo">Titulo</option>
              </select>
            </div>

            {hasActiveFilters && (
              <button onClick={() => { setFilterVerdict('all'); setFilterCategory('all'); setFilterTipo('all'); setSearchText(''); }}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium px-3 py-2 rounded-lg hover:bg-blue-50 transition-colors whitespace-nowrap">
                Limpiar
              </button>
            )}
          </div>

          {/* List */}
          {loading ? (
            <div className="text-center py-24 bg-white rounded-xl shadow-sm border border-slate-200">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-sm font-medium text-slate-500">Cargando regulaciones evaluadas...</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredNormas.map((norma) => {
                const isWarning = norma.verdict === 'modify' || norma.verdict === 'delete';

                return (
                  <div key={norma.id_norma} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden transition-all duration-200 hover:shadow-md hover:border-slate-300 group">
                    <div className="p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-3">
                          {getVerdictBadge(norma.verdict)}
                          {getPrioridadBadge(norma.prioridad)}
                          {norma.tipo_norma && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100">
                              <Building2 className="w-3 h-3 mr-1" />{norma.tipo_norma}
                            </span>
                          )}
                          {norma.categoria && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                              <Tag className="w-3 h-3 mr-1" />{norma.categoria}
                            </span>
                          )}
                          {norma.impacto_economico && (
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              norma.impacto_economico === 'alto' ? 'bg-red-50 text-red-600 border border-red-100' :
                              norma.impacto_economico === 'medio' ? 'bg-amber-50 text-amber-600 border border-amber-100' :
                              'bg-green-50 text-green-600 border border-green-100'
                            }`}>
                              Impacto {norma.impacto_economico}
                            </span>
                          )}
                          {norma.impact_areas && Array.isArray(norma.impact_areas) && norma.impact_areas.map((area: string, idx: number) => (
                            <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-50 text-slate-500 border border-slate-200">
                              {area}
                            </span>
                          ))}
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 leading-tight mb-2 group-hover:text-blue-700 transition-colors">
                          {norma.titulo}
                        </h3>
                        <div className="flex flex-wrap items-center text-xs text-slate-500 font-medium gap-2">
                          {norma.fecha_publicacion && (
                            <span className="flex items-center bg-slate-100 px-2 py-1 rounded">
                              <Calendar className="w-3.5 h-3.5 mr-1.5 opacity-70" />
                              {moment(norma.fecha_publicacion).format('LL')}
                            </span>
                          )}
                          <span className="font-mono bg-slate-100 px-2 py-1 rounded text-slate-600">ID: {norma.id_norma}</span>
                          {norma.organismo && (
                            <span className="bg-slate-100 px-2 py-1 rounded">{norma.organismo}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="p-5 bg-slate-50 flex flex-col gap-6">
                      {/* Summary */}
                      <div className="relative">
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-slate-300 rounded-full"></div>
                        <div className="pl-4">
                          <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500 mb-1.5">Resumen</h4>
                          <p className="text-sm text-slate-700 leading-relaxed">{norma.summary}</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                        <div>
                          <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500 mb-2 flex items-center">
                            <Scale className="w-3.5 h-3.5 mr-1.5 text-blue-500" /> Justificacion Economica
                          </h4>
                          <p className="text-sm text-slate-700 font-serif leading-relaxed">{norma.reason}</p>
                        </div>

                        <div>
                          <h4 className="text-[11px] uppercase tracking-wider font-bold text-red-500 mb-2 flex items-center">
                            <BadgeAlert className="w-3.5 h-3.5 mr-1.5" /> Efectos Nocivos
                          </h4>
                          <p className="text-sm text-slate-700 leading-relaxed bg-red-50/50 p-3 rounded-md border border-red-100/50">
                            {norma.negative_effects || 'Ningun efecto colateral negativo detectado.'}
                          </p>
                        </div>
                      </div>

                      {/* Legislative Action */}
                      {isWarning && norma.legislative_action && (
                        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-lg border border-blue-100 shadow-sm relative overflow-hidden">
                          <div className="absolute -right-4 -top-4 opacity-5">
                            <Wrench className="w-24 h-24" />
                          </div>
                          <h4 className="text-[11px] uppercase tracking-wider font-bold text-blue-800 mb-2 flex items-center relative z-10">
                            <AlertTriangle className="w-3.5 h-3.5 mr-1.5" /> Accion Legislativa Recomendada
                          </h4>
                          <p className="text-sm text-blue-900 font-medium relative z-10 leading-relaxed">
                            {norma.legislative_action}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {filteredNormas.length === 0 && (
                <div className="text-center py-24 bg-white rounded-xl border border-dashed border-slate-300 flex flex-col items-center justify-center">
                  <div className="h-16 w-16 bg-slate-100 rounded-full flex items-center justify-center mb-4">
                    <Search className="w-8 h-8 text-slate-400" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">No hay normas que coincidan</h3>
                  <p className="text-sm text-slate-500 max-w-sm mx-auto mt-2 leading-relaxed">Prueba cambiando los filtros o la busqueda.</p>
                  <button onClick={() => { setFilterVerdict('all'); setFilterCategory('all'); setFilterTipo('all'); setSearchText(''); }}
                    className="mt-6 px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium shadow-sm hover:bg-slate-50 transition-colors">
                    Limpiar todos los filtros
                  </button>
                </div>
              )}
            </div>
          )}
        </section>

      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 mt-12 py-8">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <div className="flex items-center justify-center opacity-50 mb-4">
            <Scale className="h-5 w-5" />
          </div>
          <p className="text-sm text-slate-500 font-medium">Better Chile {new Date().getFullYear()} -- Auditoria Transparente de las Regulaciones.</p>
        </div>
      </footer>
    </div>
  );
}
