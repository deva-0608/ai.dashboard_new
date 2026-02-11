import React, { useRef, useEffect, useState } from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import {
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  HeatmapChart, GaugeChart, FunnelChart, TreemapChart,
  BoxplotChart,
} from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, VisualMapComponent, DataZoomComponent, ToolboxComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  HeatmapChart, GaugeChart, FunnelChart, TreemapChart, BoxplotChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, VisualMapComponent, DataZoomComponent,
  ToolboxComponent, CanvasRenderer,
])

const TYPE_COLORS = {
  bar: '#6366f1', line: '#06b6d4', pie: '#f43f5e', scatter: '#10b981',
  area: '#8b5cf6', radar: '#f97316', heatmap: '#ec4899', gauge: '#14b8a6',
  funnel: '#e11d48', treemap: '#0ea5e9', boxplot: '#8b5cf6', histogram: '#f97316',
}

export default function ChartWidget({ chart }) {
  const [isHovered, setIsHovered] = useState(false)
  const chartRef = useRef(null)

  const isCartesian = !['pie', 'gauge', 'radar', 'funnel', 'treemap'].includes(chart.type)
  // boxplot and histogram are cartesian (have x/y axes)

  const enhancedOption = {
    ...chart.option,
    backgroundColor: 'transparent',
    textStyle: { color: '#57534e', fontFamily: 'Inter, sans-serif' },
    title: {
      ...(chart.option.title || {}),
      textStyle: {
        ...(chart.option.title?.textStyle || {}),
        color: '#1c1917', fontFamily: 'Inter, sans-serif',
        fontWeight: 600, fontSize: 13,
      },
      top: 10, left: 'center',
    },
    ...(isCartesian ? {
      grid: {
        ...(chart.option.grid || {}),
        left: '6%', right: '4%', bottom: '12%', top: '20%', containLabel: true,
      },
      xAxis: {
        ...(chart.option.xAxis || {}),
        axisLine: { lineStyle: { color: '#d6d3d1' } },
        axisLabel: { ...(chart.option.xAxis?.axisLabel || {}), color: '#78716c', fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        ...(chart.option.yAxis || {}),
        axisLine: { show: false },
        axisLabel: { color: '#78716c', fontSize: 10 },
        splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } },
      },
    } : {}),
    tooltip: {
      ...(chart.option.tooltip || {}),
      backgroundColor: '#fff', borderColor: '#e5e7eb', borderWidth: 1,
      textStyle: { color: '#1c1917', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-radius: 8px;',
    },
    toolbox: {
      show: true, right: 8, top: 6,
      iconStyle: { borderColor: '#c4c4c4' },
      emphasis: { iconStyle: { borderColor: '#f59e0b' } },
      feature: {
        saveAsImage: { title: 'Save', pixelRatio: 2 },
        dataZoom: { title: { zoom: 'Zoom', back: 'Reset' } },
        restore: { title: 'Reset' },
      },
    },
    legend: {
      ...(chart.option.legend || {}),
      textStyle: { color: '#78716c', fontSize: 11 },
    },
    animationDuration: 700,
    animationEasing: 'cubicOut',
  }

  useEffect(() => {
    const handleResize = () => {
      if (chartRef.current) {
        const inst = chartRef.current.getEchartsInstance()
        if (inst) inst.resize()
      }
    }
    let timer
    const observer = new ResizeObserver(() => {
      clearTimeout(timer)
      timer = setTimeout(handleResize, 80)
    })
    const el = chartRef.current?.ele
    if (el) observer.observe(el)
    return () => { clearTimeout(timer); observer.disconnect() }
  }, [])

  const accentColor = TYPE_COLORS[chart.type] || '#6366f1'

  return (
    <div
      style={{ ...styles.card, ...(isHovered ? styles.cardHover : {}) }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Drag handle bar */}
      <div className="drag-handle" style={styles.handleBar}>
        <div style={styles.handleLeft}>
          <span style={{ ...styles.typeDot, background: accentColor }} />
          <span style={styles.typeLabel}>{chart.type}</span>
        </div>
        <div style={styles.handleDots}>
          <span style={styles.dot} /><span style={styles.dot} /><span style={styles.dot} />
          <span style={styles.dot} /><span style={styles.dot} /><span style={styles.dot} />
        </div>
      </div>

      {/* Chart */}
      <div style={styles.chartWrap}>
        <ReactEChartsCore
          ref={chartRef}
          echarts={echarts}
          option={enhancedOption}
          style={{ height: '100%', width: '100%' }}
          opts={{ renderer: 'canvas' }}
          notMerge={true}
          lazyUpdate={true}
        />
      </div>
    </div>
  )
}

const styles = {
  card: {
    height: '100%', background: '#fff', borderRadius: 12,
    border: '1px solid #e5e7eb', overflow: 'hidden',
    display: 'flex', flexDirection: 'column', transition: 'all 0.15s',
    boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
  },
  cardHover: {
    borderColor: '#d1d5db',
    boxShadow: '0 4px 16px rgba(0,0,0,0.07)',
  },
  handleBar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '5px 12px', cursor: 'grab', flexShrink: 0,
    borderBottom: '1px solid #f3f4f6', background: '#fafafa',
  },
  handleLeft: { display: 'flex', alignItems: 'center', gap: 6 },
  typeDot: { width: 6, height: 6, borderRadius: 3 },
  typeLabel: {
    fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: '0.06em', color: '#9ca3af',
  },
  handleDots: {
    display: 'grid', gridTemplateColumns: 'repeat(3, 5px)', gridTemplateRows: 'repeat(2, 5px)',
    gap: 2, opacity: 0.4,
  },
  dot: { width: 3, height: 3, borderRadius: '50%', background: '#9ca3af' },
  chartWrap: { flex: 1, minHeight: 0, padding: '4px 2px 2px' },
}
