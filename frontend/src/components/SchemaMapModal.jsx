import React, { useState, useMemo, useRef, useEffect } from 'react';
import { 
  X, Database, Network, Search, Key, Link as LinkIcon, 
  Layers, FileJson, ZoomIn, ZoomOut, RotateCcw, Move
} from 'lucide-react';

export default function SchemaMapModal({ 
  isOpen, 
  onClose, 
  dbName = "Database", 
  dbType = "sql", 
  tables = [], 
  relationships = [], 
  isDark 
}) {
  const [activeTab, setActiveTab] = useState('diagram'); // 'diagram' | 'cards'
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTable, setSelectedTable] = useState(null);
  const [hoveredTable, setHoveredTable] = useState(null);
  const [hoveredRel, setHoveredRel] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [customPositions, setCustomPositions] = useState({});
  const [dragging, setDragging] = useState(null); // { tableName, startMouseX, startMouseY, origX, origY }
  const canvasRef = useRef(null);

  // 1. Filter tables based on search query
  const filteredTables = useMemo(() => {
    if (!searchQuery.trim()) return tables || [];
    const q = searchQuery.toLowerCase();
    return (tables || []).filter(t => 
      (t.name && t.name.toLowerCase().includes(q)) || 
      (t.cols && t.cols.some(c => c.toLowerCase().includes(q)))
    );
  }, [tables, searchQuery]);

  // 2. Group connections per table for quick bidirectional inspection
  const tableConnectionsMap = useMemo(() => {
    const map = {};
    (tables || []).forEach(t => {
      if (!t || !t.name) return;
      map[t.name] = {
        outgoing: (relationships || []).filter(r => r.from_table && r.from_table.toLowerCase() === t.name.toLowerCase()),
        incoming: (relationships || []).filter(r => r.to_table && r.to_table.toLowerCase() === t.name.toLowerCase())
      };
    });
    return map;
  }, [tables, relationships]);

  // 3. Calculate Visual ER Diagram Multi-Tier Topological Layout
  const erLayout = useMemo(() => {
    if (!tables || tables.length === 0) return { positions: {}, width: 1400, height: 800 };

    const tableNames = tables.map(t => t.name);
    const depthMap = {};
    
    // Classify tables by dependency depth
    tableNames.forEach(name => {
      const conn = tableConnectionsMap[name] || { outgoing: [], incoming: [] };
      const outCount = conn.outgoing.length;
      const inCount = conn.incoming.length;

      if (outCount === 0) {
        depthMap[name] = 0; // Target / Parent tables (e.g. Artist, Genre, MediaType)
      } else if (inCount === 0) {
        depthMap[name] = 2; // Leaf / detail tables (e.g. InvoiceLine, PlaylistTrack)
      } else {
        depthMap[name] = 1; // Middle connected tables (e.g. Album, Track, Invoice, Customer)
      }
    });

    // Group tables into 3 visual columns
    const columns = [[], [], []];
    tableNames.forEach(name => {
      const depth = depthMap[name] !== undefined ? depthMap[name] : 1;
      columns[depth].push(name);
    });

    const CARD_WIDTH = 260;
    const CARD_GAP_X = 160;
    const CARD_GAP_Y = 24;
    const START_X = 40;
    const START_Y = 40;

    const positions = {};
    let maxY = 600;

    columns.forEach((colTables, colIdx) => {
      let currentY = START_Y;
      const currentX = START_X + colIdx * (CARD_WIDTH + CARD_GAP_X);

      colTables.forEach(tableName => {
        const tbl = tables.find(t => t.name === tableName);
        const colCount = tbl?.columns?.length || tbl?.cols?.length || 5;
        const cardHeight = Math.min(270, 52 + colCount * 22);

        positions[tableName] = {
          x: currentX,
          y: currentY,
          width: CARD_WIDTH,
          height: cardHeight
        };

        currentY += cardHeight + CARD_GAP_Y;
      });

      if (currentY > maxY) maxY = currentY;
    });

    const maxX = START_X + columns.length * (CARD_WIDTH + CARD_GAP_X);
    return { positions, width: Math.max(1280, maxX), height: Math.max(750, maxY + 60) };
  }, [tables, tableConnectionsMap]);

  // Helper to get effective live position of a table (custom dragged or default layout)
  const getTablePos = (tableName) => {
    if (customPositions[tableName]) return customPositions[tableName];
    return erLayout.positions[tableName] || { x: 40, y: 40, width: 260, height: 200 };
  };

  // Drag Handlers
  const handleMouseDown = (e, tableName) => {
    if (e.button !== 0) return; // Only primary left click
    e.stopPropagation();
    const pos = getTablePos(tableName);
    setDragging({
      tableName,
      startMouseX: e.clientX,
      startMouseY: e.clientY,
      origX: pos.x,
      origY: pos.y
    });
  };

  useEffect(() => {
    if (!dragging) return;

    const handleMouseMove = (e) => {
      const dx = (e.clientX - dragging.startMouseX) / zoom;
      const dy = (e.clientY - dragging.startMouseY) / zoom;
      const newX = Math.max(10, Math.round(dragging.origX + dx));
      const newY = Math.max(10, Math.round(dragging.origY + dy));

      setCustomPositions(prev => ({
        ...prev,
        [dragging.tableName]: {
          ...(prev[dragging.tableName] || erLayout.positions[dragging.tableName]),
          x: newX,
          y: newY
        }
      }));
    };

    const handleMouseUp = () => {
      setDragging(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragging, zoom, erLayout.positions]);

  // 4. Calculate SVG Bezier Connector Paths with Live Stretching
  const svgPaths = useMemo(() => {
    if (!relationships || relationships.length === 0 || !erLayout.positions) return [];

    return relationships.map((rel, idx) => {
      const fromPos = getTablePos(rel.from_table);
      const toPos = getTablePos(rel.to_table);

      if (!fromPos || !toPos) return null;

      // Attach at right edge if source is to left of target, otherwise attach at left edge
      const isFromLeft = fromPos.x < toPos.x;
      const startX = isFromLeft ? fromPos.x + fromPos.width : fromPos.x;
      const startY = fromPos.y + 36 + ((idx * 17) % Math.max(20, fromPos.height - 50));

      const endX = isFromLeft ? toPos.x : toPos.x + toPos.width;
      const endY = toPos.y + 36 + ((idx * 19) % Math.max(20, toPos.height - 50));

      const dx = Math.max(40, Math.abs(endX - startX) * 0.45);
      const pathD = `M ${startX} ${startY} C ${isFromLeft ? startX + dx : startX - dx} ${startY}, ${isFromLeft ? endX - dx : endX + dx} ${endY}, ${endX} ${endY}`;

      return {
        id: `rel-${idx}`,
        rel,
        pathD,
        startX,
        startY,
        endX,
        endY
      };
    }).filter(Boolean);
  }, [relationships, erLayout, customPositions]);

  if (!isOpen) return null;

  const isExcel = dbType === 'excel';
  const isCsv = dbType === 'csv';
  const isNoSql = dbType === 'nosql';
  const activeFocusTable = selectedTable || hoveredTable;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/75 backdrop-blur-xs flex items-center justify-center p-3 md:p-6 animate-fadeIn">
      <div className={`w-full max-w-6xl rounded-2xl shadow-2xl border flex flex-col h-[92vh] transition-all overflow-hidden ${
        isDark ? 'bg-slate-900 border-slate-700/80 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
      }`}>
        {/* MODAL HEADER */}
        <div className={`flex items-center justify-between px-6 py-3.5 border-b shrink-0 ${
          isDark ? 'bg-slate-950/70 border-slate-800' : 'bg-slate-50 border-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl border ${
              isExcel
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : isCsv
                  ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
                  : isNoSql 
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' 
                    : 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'
            }`}>
              <Network className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold">Data Architecture & Schema Map</h3>
                <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase ${
                  isExcel
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                    : isCsv
                      ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20'
                      : isNoSql 
                        ? 'bg-amber-500/15 text-amber-400 border border-amber-500/20' 
                        : 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/20'
                }`}>
                  {isExcel ? 'Excel Workbook' : isCsv ? 'CSV Tabular Dataset' : isNoSql ? 'NoSQL Document Store' : 'Relational SQL Database'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Data Source: <strong className="text-indigo-400">{dbName}</strong> ({tables.length} {
                  isExcel ? 'worksheets' : isNoSql ? 'collections' : 'tables'
                }, {relationships.length} relationships)
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* TOOLBAR */}
        <div className={`flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-2.5 border-b shrink-0 ${
          isDark ? 'bg-slate-900/90 border-slate-800' : 'bg-slate-50/50 border-slate-200'
        }`}>
          {/* View Mode Toggle */}
          <div className="flex items-center p-1 rounded-xl bg-slate-800/60 border border-slate-700/60 w-full sm:w-auto">
            <button
              onClick={() => setActiveTab('diagram')}
              className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'diagram'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Network className="w-3.5 h-3.5" />
              <span>Visual ER Diagram</span>
            </button>
            <button
              onClick={() => setActiveTab('cards')}
              className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'cards'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Entity Cards Grid ({tables.length})</span>
            </button>
          </div>

          {/* Controls: Zoom, Reset Positions & Search */}
          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            {activeTab === 'diagram' && (
              <>
                <button
                  onClick={() => {
                    setCustomPositions({});
                    setZoom(1);
                  }}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-800/60 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 text-xs transition-colors cursor-pointer"
                  title="Reset all tables back to default positions"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span className="hidden md:inline">Reset Layout</span>
                </button>

                <div className="flex items-center gap-1 px-2 py-1 rounded-xl bg-slate-800/60 border border-slate-700/60 text-slate-300 text-xs font-mono">
                  <button
                    onClick={() => setZoom(z => Math.max(0.6, Math.round((z - 0.1) * 10) / 10))}
                    className="p-1 hover:text-white transition-colors cursor-pointer"
                    title="Zoom Out"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <span className="px-1 text-[11px] min-w-[36px] text-center">{Math.round(zoom * 100)}%</span>
                  <button
                    onClick={() => setZoom(z => Math.min(1.6, Math.round((z + 0.1) * 10) / 10))}
                    className="p-1 hover:text-white transition-colors cursor-pointer"
                    title="Zoom In"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                </div>
              </>
            )}

            {/* Search Box */}
            <div className="relative w-full sm:w-56">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Highlight tables or keys..."
                className={`w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border focus:outline-none focus:border-indigo-500 transition-colors ${
                  isDark ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
                }`}
              />
            </div>
          </div>
        </div>

        {/* MODAL BODY */}
        <div className="flex-1 overflow-hidden relative">
          {/* TAB 1: DRAGGABLE VISUAL ER DIAGRAM CANVAS */}
          {activeTab === 'diagram' && (
            <div 
              ref={canvasRef}
              className="w-full h-full overflow-auto custom-scrollbar p-6 bg-radial from-indigo-950/10 via-transparent to-transparent select-none cursor-default"
            >
              <div 
                style={{ 
                  transform: `scale(${zoom})`, 
                  transformOrigin: 'top left',
                  width: erLayout.width,
                  height: erLayout.height,
                  position: 'relative'
                }}
                className="transition-transform duration-75 ease-out"
              >
                {/* SVG CONNECTOR LINES LAYER */}
                <svg 
                  className="absolute inset-0 pointer-events-none z-10 overflow-visible"
                  width={erLayout.width}
                  height={erLayout.height}
                >
                  <defs>
                    {/* Default Arrow Marker */}
                    <marker
                      id="arrow-default"
                      viewBox="0 0 10 10"
                      refX="6"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 1 L 8 5 L 0 9 z" fill="#6366f1" opacity="0.6" />
                    </marker>

                    {/* Active Glowing Arrow Marker */}
                    <marker
                      id="arrow-active"
                      viewBox="0 0 10 10"
                      refX="6"
                      refY="5"
                      markerWidth="7"
                      markerHeight="7"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 1 L 8 5 L 0 9 z" fill="#818cf8" />
                    </marker>
                  </defs>

                  {/* Render Curved Bezier Connection Lines */}
                  {svgPaths.map(({ id, rel, pathD }) => {
                    const isFromActive = activeFocusTable && rel.from_table.toLowerCase() === activeFocusTable.toLowerCase();
                    const isToActive = activeFocusTable && rel.to_table.toLowerCase() === activeFocusTable.toLowerCase();
                    const isLineActive = isFromActive || isToActive || (hoveredRel && hoveredRel === id);

                    const strokeColor = isLineActive ? '#818cf8' : (isDark ? 'rgba(99, 102, 241, 0.35)' : 'rgba(99, 102, 241, 0.45)');
                    const strokeWidth = isLineActive ? 3 : 1.75;
                    const strokeOpacity = activeFocusTable ? (isLineActive ? 1 : 0.15) : 0.7;

                    return (
                      <g key={id} className="transition-all duration-200">
                        {/* Invisible thicker path for easier hover */}
                        <path
                          d={pathD}
                          fill="none"
                          stroke="transparent"
                          strokeWidth={14}
                          className="pointer-events-auto cursor-pointer"
                          onMouseEnter={() => setHoveredRel(id)}
                          onMouseLeave={() => setHoveredRel(null)}
                        />

                        {/* Visible Curved Bezier Connector */}
                        <path
                          d={pathD}
                          fill="none"
                          stroke={strokeColor}
                          strokeWidth={strokeWidth}
                          strokeOpacity={strokeOpacity}
                          markerEnd={isLineActive ? 'url(#arrow-active)' : 'url(#arrow-default)'}
                          className="pointer-events-none"
                        />
                      </g>
                    );
                  })}
                </svg>

                {/* DRAGGABLE TABLE NODES LAYER */}
                {tables.map(tbl => {
                  const pos = getTablePos(tbl.name);
                  const conn = tableConnectionsMap[tbl.name] || { outgoing: [], incoming: [] };
                  const isSelected = selectedTable === tbl.name;
                  const isHovered = hoveredTable === tbl.name;
                  const isConnectedToFocus = activeFocusTable && (
                    conn.outgoing.some(r => r.to_table.toLowerCase() === activeFocusTable.toLowerCase()) ||
                    conn.incoming.some(r => r.from_table.toLowerCase() === activeFocusTable.toLowerCase())
                  );

                  const isDimmed = activeFocusTable && !isSelected && !isHovered && !isConnectedToFocus;
                  const isHighlighted = isSelected || isHovered || isConnectedToFocus;
                  const isBeingDragged = dragging && dragging.tableName === tbl.name;

                  return (
                    <div
                      key={tbl.name}
                      style={{
                        position: 'absolute',
                        left: pos.x,
                        top: pos.y,
                        width: pos.width,
                        zIndex: isBeingDragged ? 50 : (isHighlighted ? 30 : 20)
                      }}
                      onClick={() => setSelectedTable(isSelected ? null : tbl.name)}
                      onMouseEnter={() => setHoveredTable(tbl.name)}
                      onMouseLeave={() => setHoveredTable(null)}
                      className={`rounded-2xl border transition-shadow duration-150 overflow-hidden shadow-md ${
                        isHighlighted
                          ? 'border-indigo-500 ring-2 ring-indigo-500/30 shadow-indigo-500/10'
                          : isDark ? 'bg-slate-950/90 border-slate-800 hover:border-slate-700' : 'bg-white border-slate-200 hover:border-slate-300'
                      } ${isDimmed ? 'opacity-30' : 'opacity-100'} ${isBeingDragged ? 'shadow-2xl scale-[1.02]' : ''}`}
                    >
                      {/* Node Header (Draggable Handle) */}
                      <div 
                        onMouseDown={(e) => handleMouseDown(e, tbl.name)}
                        className={`px-3.5 py-2.5 border-b flex items-center justify-between cursor-grab active:cursor-grabbing select-none transition-colors ${
                          isHighlighted
                            ? isDark ? 'bg-indigo-950/60 border-indigo-500/40 text-indigo-200' : 'bg-indigo-50 border-indigo-200 text-indigo-900'
                            : isDark ? 'bg-slate-900/90 border-slate-800 text-slate-200 hover:bg-slate-800/80' : 'bg-slate-50 border-slate-200 text-slate-800 hover:bg-slate-100'
                        }`}
                        title="Click and drag to move this table anywhere"
                      >
                        <div className="flex items-center gap-2 truncate">
                          <Move className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          {isNoSql ? (
                            <FileJson className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          ) : (
                            <Database className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                          )}
                          <h4 className="font-bold text-xs font-mono truncate">{tbl.name}</h4>
                        </div>

                        <span className="text-[10px] text-slate-400 font-mono shrink-0">
                          {tbl.cols ? `${tbl.cols.length} fields` : ''}
                        </span>
                      </div>

                      {/* Columns List with PK & FK Indicators */}
                      <div className="p-2.5 space-y-1 max-h-52 overflow-y-auto custom-scrollbar font-mono text-[11px] select-text">
                        {tbl.columns && tbl.columns.length > 0 ? (
                          tbl.columns.map((c, cIdx) => (
                            <div key={cIdx} className="flex items-center justify-between gap-1 py-0.5 px-1 rounded hover:bg-slate-800/40">
                              <div className="flex items-center gap-1.5 truncate">
                                {c.is_pk ? (
                                  <Key className="w-3 h-3 text-amber-400 shrink-0" title="Primary Key" />
                                ) : c.is_fk ? (
                                  <LinkIcon className="w-3 h-3 text-indigo-400 shrink-0" title="Foreign Key" />
                                ) : (
                                  <span className="w-2.5 inline-block" />
                                )}
                                <span className={`truncate ${c.is_pk ? 'font-bold text-amber-300' : c.is_fk ? 'font-semibold text-indigo-400' : 'text-slate-300'}`}>
                                  {c.name}
                                </span>
                              </div>

                              <div className="flex items-center gap-1 shrink-0 text-[10px]">
                                <span className="text-slate-500 text-[9px]">{c.type}</span>
                                {c.is_fk && c.fk_to_table && (
                                  <span className="px-1 py-0.2 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-[9px]">
                                    ➔ {c.fk_to_table}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))
                        ) : (
                          tbl.cols && tbl.cols.map((colStr, cIdx) => (
                            <div key={cIdx} className="text-slate-300 truncate py-0.5 px-1 text-[10px]">
                              {colStr}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: ENTITY CARDS GRID VIEW */}
          {activeTab === 'cards' && (
            <div className="h-full overflow-y-auto p-6 custom-scrollbar">
              {filteredTables.length === 0 ? (
                <div className="text-center py-12 text-slate-400 text-xs">
                  No tables match your search query.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredTables.map((tbl) => {
                    const conn = tableConnectionsMap[tbl.name] || { outgoing: [], incoming: [] };
                    const hasConnections = conn.outgoing.length > 0 || conn.incoming.length > 0;
                    const isSelected = selectedTable === tbl.name;

                    return (
                      <div 
                        key={tbl.name}
                        onClick={() => setSelectedTable(isSelected ? null : tbl.name)}
                        className={`rounded-2xl border overflow-hidden transition-all flex flex-col cursor-pointer ${
                          isSelected
                            ? 'border-indigo-500 ring-2 ring-indigo-500/20 shadow-lg'
                            : isDark ? 'bg-slate-950/60 border-slate-800 hover:border-slate-700' : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
                        }`}
                      >
                        {/* Table Header */}
                        <div className={`px-4 py-3 border-b flex items-center justify-between ${
                          isDark ? 'bg-slate-900/80 border-slate-800' : 'bg-slate-50 border-slate-200'
                        }`}>
                          <div className="flex items-center gap-2 truncate pr-2">
                            {isNoSql ? (
                              <FileJson className="w-4 h-4 text-amber-400 shrink-0" />
                            ) : (
                              <Database className="w-4 h-4 text-indigo-400 shrink-0" />
                            )}
                            <h4 className="font-bold text-xs font-mono truncate">{tbl.name}</h4>
                          </div>

                          <span className="text-[10px] text-slate-400 shrink-0 font-mono">
                            {tbl.cols ? `${tbl.cols.length} fields` : ''}
                          </span>
                        </div>

                        {/* Connection Badges */}
                        {hasConnections && (
                          <div className={`px-3 py-1.5 text-[10px] border-b flex flex-wrap gap-1 ${
                            isDark ? 'bg-slate-900/40 border-slate-800/60 text-slate-400' : 'bg-slate-100/60 border-slate-200 text-slate-600'
                          }`}>
                            {conn.outgoing.map((out, idx) => (
                              <span key={idx} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono">
                                <LinkIcon className="w-2.5 h-2.5" /> ➔ {out.to_table}
                              </span>
                            ))}
                            {conn.incoming.map((inc, idx) => (
                              <span key={idx} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                                ⬅ {inc.from_table}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Columns */}
                        <div className="p-3 space-y-1 flex-1 max-h-56 overflow-y-auto custom-scrollbar font-mono text-[11px]">
                          {tbl.columns && tbl.columns.length > 0 ? (
                            tbl.columns.map((c, cIdx) => (
                              <div key={cIdx} className="flex items-center justify-between gap-2 py-0.5">
                                <div className="flex items-center gap-1.5 truncate">
                                  {c.is_pk ? (
                                    <Key className="w-3 h-3 text-amber-400 shrink-0" title="Primary Key" />
                                  ) : c.is_fk ? (
                                    <LinkIcon className="w-3 h-3 text-indigo-400 shrink-0" title="Foreign Key" />
                                  ) : (
                                    <span className="w-3 inline-block" />
                                  )}
                                  <span className={`truncate ${c.is_pk ? 'font-bold text-amber-300' : c.is_fk ? 'font-semibold text-indigo-400' : 'text-slate-300'}`}>
                                    {c.name}
                                  </span>
                                </div>

                                <div className="flex items-center gap-1 shrink-0 text-[10px]">
                                  <span className="text-slate-500">{c.type}</span>
                                  {c.is_fk && c.fk_to_table && (
                                    <span className="px-1.5 py-0.2 rounded bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
                                      ➔ {c.fk_to_table}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))
                          ) : (
                            tbl.cols && tbl.cols.map((colStr, cIdx) => (
                              <div key={cIdx} className="text-slate-300 truncate py-0.5">
                                {colStr}
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* MODAL FOOTER */}
        <div className={`flex items-center justify-between px-6 py-3 border-t shrink-0 text-xs text-slate-400 ${
          isDark ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200'
        }`}>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-amber-400" /> Primary Key (PK)
            </span>
            <span className="flex items-center gap-1.5">
              <LinkIcon className="w-3.5 h-3.5 text-indigo-400" /> Foreign Key (FK)
            </span>
            <span className="hidden sm:inline text-slate-400">
              ✋ <strong>Drag any card's header</strong> to arrange tables freely! Connected lines follow in real time.
            </span>
          </div>

          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors cursor-pointer text-xs font-semibold"
          >
            Close Diagram
          </button>
        </div>
      </div>
    </div>
  );
}
