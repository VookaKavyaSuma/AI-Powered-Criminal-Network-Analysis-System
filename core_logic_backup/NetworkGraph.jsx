import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import cytoscape from 'cytoscape';
import { ZoomIn, ZoomOut, Maximize2, Download, RotateCcw, Eye } from 'lucide-react';

const NODE_COLORS = {
  Person: '#3b82f6',       // Blue
  PhoneNumber: '#10b981',  // Emerald Green
  Phone: '#10b981',
  Vehicle: '#f97316',      // Orange
  Account: '#a855f7',      // Purple
  Organization: '#ef4444', // Red
  Org: '#ef4444',
  Location: '#64748b',     // Slate Gray
  Event: '#eab308',        // Amber
  Default: '#64748b',
};

const NODE_SHAPES = {
  Person: 'ellipse',
  PhoneNumber: 'diamond',
  Phone: 'diamond',
  Vehicle: 'round-rectangle',
  Account: 'hexagon',
  Organization: 'rectangle',
  Org: 'rectangle',
  Location: 'triangle',
  Event: 'star',
  Default: 'ellipse',
};

export function NetworkGraph({
  elements = [],
  onNodeClick,
  onEdgeClick,
  height = '500px',
  layoutName = 'cose',
  showControls = true,
  isLoading = false,
  className = '',
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [currentLayout, setCurrentLayout] = useState(layoutName);

  const hasElements = useMemo(() => {
    if (!elements) return false;
    if (Array.isArray(elements)) return elements.length > 0;
    if (elements.elements?.nodes) return elements.elements.nodes.length > 0;
    if (elements.nodes) return elements.nodes.length > 0;
    return false;
  }, [elements]);

  // Initialize or update Cytoscape instance
  useEffect(() => {
    if (!containerRef.current) return;

    // Normalizing elements to cytoscape format if raw neo4j/cytoscape json
    let cyElements = [];
    if (Array.isArray(elements)) {
      cyElements = elements;
    } else if (elements?.elements?.nodes && elements?.elements?.edges) {
      cyElements = [...elements.elements.nodes, ...elements.elements.edges];
    } else if (elements?.nodes && elements?.edges) {
      cyElements = [...elements.nodes, ...elements.edges];
    }

    // Destroy existing instance if any
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: cyElements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        {
          selector: 'node',
          style: {
            'label': (ele) => ele.data('name') || ele.data('display_name') || ele.data('label') || ele.data('id') || '',
            'color': '#334155',
            'font-family': 'JetBrains Mono, monospace',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'background-color': (ele) => {
              const type = ele.data('type') || ele.data('label_type') || 'Default';
              return NODE_COLORS[type] || NODE_COLORS.Default;
            },
            'shape': (ele) => {
              const type = ele.data('type') || ele.data('label_type') || 'Default';
              return NODE_SHAPES[type] || NODE_SHAPES.Default;
            },
            'width': (ele) => {
              const risk = ele.data('risk_score');
              if (risk !== undefined && risk !== null) {
                return Math.max(28, Math.min(60, 28 + (risk / 100) * 32));
              }
              return 32;
            },
            'height': (ele) => {
              const risk = ele.data('risk_score');
              if (risk !== undefined && risk !== null) {
                return Math.max(28, Math.min(60, 28 + (risk / 100) * 32));
              }
              return 32;
            },
            'border-width': 2,
            'border-color': (ele) => {
              const risk = ele.data('risk_score');
              if (risk >= 75) return '#ef4444';
              if (risk >= 50) return '#f59e0b';
              return '#FFD9C7';
            },
            'border-opacity': 0.9,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#ffffff',
            'overlay-color': '#3b82f6',
            'overlay-opacity': 0.3,
            'overlay-padding': 6,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': (ele) => {
              const calls = ele.data('calls') || ele.data('weight') || 1;
              return Math.min(6, Math.max(1.5, Math.log2(calls + 1) * 1.5));
            },
            'line-color': (ele) => {
              const label = ele.data('label') || ele.data('type') || '';
              if (label === 'CALLED') return '#3b82f6';
              if (label === 'TRANSFERRED_MONEY_TO') {
                return ele.data('flagged_structuring') ? '#f59e0b' : '#10b981';
              }
              if (label === 'OWNS_OR_USES') return '#64748b';
              return '#475569';
            },
            'target-arrow-color': (ele) => {
              const label = ele.data('label') || ele.data('type') || '';
              if (label === 'CALLED') return '#3b82f6';
              if (label === 'TRANSFERRED_MONEY_TO') {
                return ele.data('flagged_structuring') ? '#f59e0b' : '#10b981';
              }
              if (label === 'OWNS_OR_USES') return '#64748b';
              return '#475569';
            },
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8,
            'opacity': 0.75,
            'font-size': '8px',
            'font-family': 'monospace',
            'color': '#64748b',
            'text-rotation': 'autorotate',
            'text-margin-y': -6,
            'label': (ele) => {
              const label = ele.data('label') || ele.data('type');
              const amount = ele.data('amount');
              if (amount) return `₹${Number(amount).toLocaleString('en-IN')}`;
              return label || '';
            },
            'line-style': (ele) => {
              const label = ele.data('label') || ele.data('type');
              if (label === 'TRANSFERRED_MONEY_TO') return 'dashed';
              if (label === 'ASSOCIATED_WITH') return 'dotted';
              return 'solid';
            },
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#ffffff',
            'target-arrow-color': '#ffffff',
            'width': 4,
            'opacity': 1,
          },
        },
      ],
      layout: {
        name: currentLayout,
        animate: false, // Instant calculation for reliable initial render
        fit: true,
        padding: 40,
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: 100,
        nodeRepulsion: 450000,
      },
    });

    // Event listeners
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      if (onNodeClick) onNodeClick(node.data());
    });

    cy.on('tap', 'edge', (evt) => {
      const edge = evt.target;
      if (onEdgeClick) onEdgeClick(edge.data());
    });

    cyRef.current = cy;

    // Force post-paint resize and fit to avoid zero-dimension container bug
    const rafId = requestAnimationFrame(() => {
      if (cyRef.current) {
        cyRef.current.resize();
        cyRef.current.fit(undefined, 40);
      }
    });

    const timerId = setTimeout(() => {
      if (cyRef.current) {
        cyRef.current.resize();
        cyRef.current.fit(undefined, 40);
      }
    }, 150);

    // Watch for flexbox/panel size changes
    let ro;
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      ro = new ResizeObserver(() => {
        if (cyRef.current) {
          cyRef.current.resize();
        }
      });
      ro.observe(containerRef.current);
    }

    return () => {
      cancelAnimationFrame(rafId);
      clearTimeout(timerId);
      if (ro) ro.disconnect();
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [elements, currentLayout, onNodeClick, onEdgeClick]);

  // Layout switcher
  const changeLayout = useCallback((layout) => {
    setCurrentLayout(layout);
    if (cyRef.current) {
      cyRef.current.layout({ name: layout, animate: true, fit: true, padding: 40 }).run();
    }
  }, []);

  const handleZoomIn = () => cyRef.current && cyRef.current.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current && cyRef.current.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current && cyRef.current.fit(undefined, 30);
  const handleCenter = () => cyRef.current && cyRef.current.center();

  const handleExportPng = () => {
    if (!cyRef.current) return;
    const png64 = cyRef.current.png({ bg: '#FFF8F5', full: true, scale: 2 });
    const a = document.createElement('a');
    a.href = png64;
    a.download = `cna-graph-export-${Date.now()}.png`;
    a.click();
  };

  const resolvedHeight = height === '100%' ? '100%' : (typeof height === 'number' ? `${height}px` : height);

  return (
    <div
      className={`relative w-full h-full flex-1 border border-slate-100 rounded-2xl overflow-hidden bg-white flex flex-col ${className}`}
      style={{
        height: resolvedHeight,
        minHeight: height === '100%' ? '450px' : resolvedHeight,
      }}
    >
      {/* Cytoscape Canvas Container */}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          minHeight: height === '100%' ? '450px' : resolvedHeight,
        }}
        className="w-full h-full flex-1 cytoscape-container grid-bg cursor-grab active:cursor-grabbing"
      />

      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-white/85 backdrop-blur-xs text-peach-500 font-sans text-xs gap-2">
          <RotateCcw className="w-5 h-5 animate-spin text-peach-500" />
          <span className="tracking-wider uppercase font-semibold">Synchronizing network topology...</span>
        </div>
      )}

      {/* Floating Control Toolbar */}
      {showControls && (
        <div className="absolute top-3 left-3 z-10 flex items-center gap-1 p-1 bg-white/90 border border-slate-100 rounded-2xl shadow-md backdrop-blur-sm">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-peach-50 rounded-2xl transition-colors"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-peach-50 rounded-2xl transition-colors"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleFit}
            title="Fit to Screen"
            className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-peach-50 rounded-2xl transition-colors"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleCenter}
            title="Recenter"
            className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-peach-50 rounded-2xl transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <div className="h-4 w-px bg-peach-200 mx-1" />

          {/* Layout Selector */}
          <select
            value={currentLayout}
            onChange={(e) => changeLayout(e.target.value)}
            className="bg-peach-50 border border-slate-100 text-[11px] font-sans text-slate-700 py-1 px-2 rounded-2xl focus:outline-none focus:border-blue-500"
          >
            <option value="cose">Force Directed (CoSE)</option>
            <option value="concentric">Concentric Rings</option>
            <option value="circle">Circular Network</option>
            <option value="breadthfirst">Hierarchical Tree</option>
            <option value="grid">Orthogonal Grid</option>
          </select>

          <div className="h-4 w-px bg-peach-200 mx-1" />

          <button
            onClick={handleExportPng}
            title="Export High-Res PNG"
            className="flex items-center gap-1 px-2 py-1 text-[11px] font-sans text-slate-600 hover:text-slate-800 bg-peach-50 hover:bg-peach-100 rounded-2xl border border-slate-100 transition-colors"
          >
            <Download className="w-3 h-3 text-peach-500" />
            <span>PNG</span>
          </button>
        </div>
      )}

      {/* Floating Legend in bottom left */}
      <div className="absolute bottom-3 left-3 z-10 hidden sm:flex flex-wrap items-center gap-2 p-2 bg-white/90 border border-slate-100 rounded-2xl text-[10px] font-sans text-slate-600 shadow-sm backdrop-blur-sm pointer-events-none">
        <span className="font-semibold text-slate-500 uppercase tracking-wider">Entities:</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" />Person</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-2xl rotate-45 bg-emerald-500" />Phone</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-2xl bg-orange-500" />Vehicle</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-2xl bg-purple-500" />Account</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500" />Org</span>
      </div>

      {/* Empty State */}
      {!hasElements && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-slate-500 font-sans text-xs">
          <Eye className="w-8 h-8 mb-2 opacity-40" />
          <span>NO SUBGRAPH DATA AVAILABLE FOR VISUALIZATION</span>
        </div>
      )}
    </div>
  );
}
