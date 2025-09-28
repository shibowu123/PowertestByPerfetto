import os
import argparse
import json
from typing import List, Dict

# 允许复用 main.py 中的提取函数
from main import Power_consumption_data_processing


def load_power_rails_from_trace(trace_path: str) -> List[Dict]:
    proc = Power_consumption_data_processing(trace=trace_path)
    data = proc.extract_power_rails_data()
    return data


def build_comparison(traces: List[str]) -> Dict:
    trace_labels = [os.path.splitext(os.path.basename(p))[0] for p in traces]
    rails: Dict[str, Dict[str, Dict[str, float]]] = {}
    for t_idx, tpath in enumerate(traces):
        label = trace_labels[t_idx]
        rows = load_power_rails_from_trace(tpath)
        for row in rows:
            rail = row.get('label', '')
            try:
                avg = float(row.get('avg_power', 0.0))
            except Exception:
                avg = 0.0
            try:
                total = float(row.get('total_power', 0.0))
            except Exception:
                total = 0.0
            rails.setdefault(rail, {})[label] = {
                'avg_power': avg,
                'total_power': total,
            }
    return {
        'trace_labels': trace_labels,
        'rails': rails,
    }


def render_horizontal_bar_svg(values: List[float], labels: List[str], width: int = 700, height_per_bar: int = 22, left_pad: int = 10, right_pad: int = 10) -> str:

    n = len(values)
    chart_h = n * height_per_bar + 10
    max_v = max(values) if values else 1.0

    if max_v <= 0:
        max_v = 1.0
    inner_w = width - left_pad - right_pad
    svg_parts = [f'<svg width="{width}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg">']
    y = 5
    for i in range(n):
        val = values[i]
        bar_w = int(inner_w * (val / max_v))
        svg_parts.append(f'<rect x="{left_pad}" y="{y}" width="{bar_w}" height="{height_per_bar-4}" fill="#4a90e2" rx="3" />')

        svg_parts.append(f'<text x="{left_pad + 6}" y="{y + height_per_bar - 8}" fill="#fff" font-size="12">{labels[i]}</text>')

        val_text = f"{val:.3f}"
        y_text = y + height_per_bar - 8
        if bar_w >= inner_w * 0.75:
            x_text = left_pad + bar_w - 6
            svg_parts.append(f'<text x="{x_text}" y="{y_text}" fill="#fff" font-size="12" text-anchor="end">{val_text}</text>')
        else:
            x_out = left_pad + bar_w + 6
            max_x = width - right_pad - 4
            if x_out <= max_x:
                svg_parts.append(f'<text x="{x_out}" y="{y_text}" fill="#333" font-size="12" text-anchor="start">{val_text}</text>')
            else:
                svg_parts.append(f'<text x="{max_x}" y="{y_text}" fill="#333" font-size="12" text-anchor="end">{val_text}</text>')
        y += height_per_bar
    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def generate_compare_html(comp: Dict, out_path: str, metric: str = 'avg_power') -> None:
    trace_labels = comp['trace_labels']
    rails_map = comp['rails']

    def rail_max_metric(rail_values: Dict[str, Dict[str, float]]) -> float:
        return max((vals.get(metric, 0.0) for vals in rail_values.values()), default=0.0)

    sorted_rails = sorted(rails_map.items(), key=lambda kv: rail_max_metric(kv[1]), reverse=True)

    thead_cols = ''.join([f'<th>{lab}</th>' for lab in trace_labels])
    table_rows = []
    charts = []

    totals = {lab: 0.0 for lab in trace_labels}
    for _, trace_map in rails_map.items():
        for lab in trace_labels:
            try:
                totals[lab] += float(trace_map.get(lab, {}).get(metric, 0.0))
            except Exception:
                pass

    total_tds = ''.join([f'<td>{totals[lab]:.3f}</td>' for lab in trace_labels])
    table_rows.append(f'<tr><td class="rail-name">总计</td>{total_tds}</tr>')

    for rail_name, trace_map in sorted_rails:

        tds = []
        values_for_chart = []
        for lab in trace_labels:
            v = trace_map.get(lab, {}).get(metric, 0.0)
            tds.append(f'<td>{v:.3f}</td>')
            values_for_chart.append(v)
        table_rows.append(f'<tr><td class="rail-name">{rail_name}</td>{"".join(tds)}</tr>')
        chart_svg = render_horizontal_bar_svg(values_for_chart, trace_labels, width=760)
        charts.append(f'<div class="chart-item"><div class="chart-title">{rail_name}</div>{chart_svg}</div>')

    tpl_path = os.path.join(os.path.dirname(__file__), 'config/compare_report_template.html')
    with open(tpl_path, 'r', encoding='utf-8') as f:
        tpl = f.read()
    
    html_content = (
        tpl
        .replace('__METRIC__', metric)
        .replace('__TRACE_LABELS__', ', '.join(trace_labels))
        .replace('__THEAD_COLS__', thead_cols)
        .replace('__TABLE_ROWS__', ''.join(table_rows))
        .replace('__CHARTS__', ''.join(charts))
    )
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"对比报告已生成: {out_path}")


from typing import List

def expand_trace_paths(paths: List[str]) -> List[str]:
    expanded: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for name in os.listdir(p):
                fp = os.path.join(p, name)
                if os.path.isfile(fp) and (fp.lower().endswith('.pftrace') or fp.lower().endswith('.trace')):
                    expanded.append(fp)
        else:
            expanded.append(p)
    seen = set()
    unique = []
    for f in expanded:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def main():
    parser = argparse.ArgumentParser(description='对比多个 Trace 的 Power Rails 数据并生成 HTML 报告')
    parser.add_argument('--traces', nargs='+', required=True, help='多个 trace(.pftrace/.trace) 文件路径或包含这些扩展名的目录（仅扫描一层）')
    parser.add_argument('--out', type=str, default='compare_report.html', help='输出 HTML 文件路径')
    parser.add_argument('--metric', type=str, choices=['avg_power', 'total_power'], default='avg_power', help='对比指标：avg_power(默认) 或 total_power')
    args = parser.parse_args()

    trace_files = expand_trace_paths(args.traces)
    if not trace_files:
        print('[ERROR] 未找到任何 .pftrace 文件。请传入若干 trace 文件或包含 .pftrace 的目录。')
        return

    comp = build_comparison(trace_files)
    generate_compare_html(comp, args.out, metric=args.metric)


if __name__ == '__main__':
    main()