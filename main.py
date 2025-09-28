from perfetto.trace_processor import TraceProcessor
import argparse
import json


class Power_consumption_data_processing():

    def __init__(self, trace=None):
        if trace is not None:
            self.trace = trace
        else:
            parser = argparse.ArgumentParser(description="参数以--开头")
            parser.add_argument('--trace', type=str, help='trace文件名称')
            args = parser.parse_args()
            self.trace = args.trace or 'trace.pftrace'


    def get_counter_fields(self):
        tp = TraceProcessor(trace=self.trace)
        rows = tp.query('PRAGMA table_info(counter)')
        for row in rows:
            print(row)

    def extract_battery_data(self):
        tp = TraceProcessor(trace=self.trace)
        rows = tp.query(
            """
            SELECT c.ts AS ts, c.value AS value, ct.name AS name, ct.unit AS unit
            FROM counter AS c
            JOIN counter_track AS ct ON c.track_id = ct.id
            WHERE lower(ct.name) IN ('batt.current_ua','batt.capacity_pct','batt.charge_uah')
            """
        )
        by_label = {}
        for row in rows:
            name = getattr(row, 'name', '')
            by_label.setdefault(name, {'values': [], 'ts': [], 'unit': getattr(row, 'unit', '')})
            by_label[name]['values'].append(getattr(row, 'value', 0.0))
            by_label[name]['ts'].append(getattr(row, 'ts', 0))
            by_label[name]['unit'] = getattr(row, 'unit', by_label[name]['unit'])
        battery_data = []
        for label, series in by_label.items():
            values = series['values']
            ts_list = series['ts']

            paired = sorted(zip(ts_list, values), key=lambda p: p[0])
            ts_sorted = [p[0] for p in paired]
            vals_sorted = [p[1] for p in paired]
            count = len(vals_sorted)
            duration = ((ts_sorted[-1] - ts_sorted[0]) / 1e9) if count > 1 else 0.0

            weighted_sum = 0.0
            total_dt = 0.0
            for i in range(1, count):
                dt = (ts_sorted[i] - ts_sorted[i-1]) / 1e9
                if dt <= 0:
                    continue
                total_dt += dt
                weighted_sum += ((vals_sorted[i-1] + vals_sorted[i]) / 2.0) * dt
            weighted_avg = (weighted_sum / total_dt) if total_dt > 0 else (sum(vals_sorted) / count if count else 0.0)
            first_value = vals_sorted[0] if count else 0.0
            last_value = vals_sorted[-1] if count else 0.0
            delta_value = last_value - first_value
            rate_per_s = (delta_value / total_dt) if total_dt > 0 else 0.0
            min_value = min(vals_sorted) if count else 0.0
            max_value = max(vals_sorted) if count else 0.0
            battery_data.append({
                "label": label,
                "delta_value": f"{delta_value:.3f}",
                "rate_per_s": f"{rate_per_s:.3f}",
                "weighted_avg_value": f"{weighted_avg:.3f}",
                "count": f"{count}",
                "first_value": f"{first_value:.3f}",
                "last_value": f"{last_value:.3f}",
                "min_value": f"{min_value:.3f}",
                "max_value": f"{max_value:.3f}"
            })
        return battery_data

    def extract_power_rails_data(self):
        tp = TraceProcessor(trace=self.trace)

        rows = tp.query(
            """
            SELECT c.ts AS ts, c.value AS value, ct.name AS name, ct.unit AS unit
            FROM counter AS c
            JOIN counter_track AS ct ON c.track_id = ct.id
            WHERE lower(ct.name) LIKE '%power%' OR lower(ct.name) LIKE '%rail%'
            """
        )
        by_label = {}
        global_min_ts = None
        global_max_ts = None
        for row in rows:
            name = getattr(row, 'name', '')
            by_label.setdefault(name, {'values': [], 'ts': []})
            ts = getattr(row, 'ts', 0)
            val = getattr(row, 'value', 0.0)
            by_label[name]['values'].append(val)
            by_label[name]['ts'].append(ts)

            if global_min_ts is None or ts < global_min_ts:
                global_min_ts = ts
            if global_max_ts is None or ts > global_max_ts:
                global_max_ts = ts
        power_rails_data = []
        global_duration = 0.0
        if global_min_ts is not None and global_max_ts is not None and global_max_ts > global_min_ts:
            global_duration = (global_max_ts - global_min_ts) / 1e9
        start_ns_global = global_min_ts if global_min_ts is not None else 0
        for label, series in by_label.items():
            paired = sorted(zip(series['ts'], series['values']), key=lambda p: p[0])
            ts_list = [p[0] for p in paired]
            values = [p[1] for p in paired]
            duration = ((ts_list[-1] - ts_list[0]) / 1e9) if ts_list else 0.0
            interval_powers = []
            points = []
            total_energy = 0.0
            start_ns = ts_list[0] if ts_list else 0
            for i in range(1, len(values)):
                dt_sec = (ts_list[i] - ts_list[i-1]) / 1e9
                if dt_sec <= 0:
                    continue
                de = values[i] - values[i-1]
                if de < 0:
                    continue
                total_energy += de
                p_uW = de / dt_sec
                p_mW = p_uW / 1000.0
                interval_powers.append(p_mW)
                rel_t_sec = (ts_list[i] - start_ns) / 1e9
                points.append({"x": rel_t_sec, "y": p_mW})
            avg_power = (total_energy / duration) / 1000.0 if duration > 0 else (sum(interval_powers) / len(interval_powers) if interval_powers else 0.0)
            total_energy_mJ = total_energy / 1000.0
            power_rails_data.append({
                "label": label,
                "duration": f"{duration:.6f}s",
                "avg_power": f"{avg_power:.3f}",
                "total_power": f"{total_energy_mJ:.3f}",
                "series_points": points
            })
        return power_rails_data

    def extract_frequency_data(self):
        tp = TraceProcessor(trace=self.trace)
        rows = tp.query(
            """
            SELECT ts AS ts, value AS value, name AS name, unit AS unit
            FROM counters
            WHERE lower(name) LIKE '%power%' OR lower(name) LIKE '%rail%'
            """
        )
        rows = tp.query(
            """
            SELECT ts AS ts, value AS value, name AS name, unit AS unit
            FROM counters
            WHERE lower(name) LIKE '%clock%' OR lower(name) LIKE '%freq%'
            """
        )
        by_label = {}
        for row in rows:
            name = getattr(row, 'name', '')
            by_label.setdefault(name, {'values': []})
            by_label[name]['values'].append(getattr(row, 'value', 0.0))
        frequency_data = []
        for label, series in by_label.items():
            values = series['values']
            avg_freq = sum(values) / len(values) if values else 0.0
            max_freq = max(values) if values else 0.0
            min_freq = min(values) if values else 0.0
            frequency_data.append({
                "label": label,
                "avg_freq": f"{avg_freq:.3f}",
                "max_freq": f"{max_freq:.3f}",
                "min_freq": f"{min_freq:.3f}"
            })
        return frequency_data

    def run(self):
        battery_data = self.extract_battery_data()
        power_rails_data = self.extract_power_rails_data()
        frequency_data = self.extract_frequency_data()
        self.generate_html_report(battery_data, power_rails_data, frequency_data)

    def generate_html_report(self, battery_data, power_rails_data, frequency_data):
        with open("config/report_template.html", "r", encoding="utf-8") as f:
            html = f.read()
        battery_rows = '\n'.join([
            f'<tr><td>{row["label"]}</td><td>{row["delta_value"]}</td><td>{row["rate_per_s"]}</td><td>{row["weighted_avg_value"]}</td><td>{row["count"]}</td><td>{row["first_value"]}</td><td>{row["last_value"]}</td><td>{row["min_value"]}</td><td>{row["max_value"]}</td></tr>'
            for row in battery_data
        ])

        power_rails_data = sorted(power_rails_data, key=lambda r: float(r.get("avg_power", 0.0)), reverse=True)

        def _parse_duration(d):
            try:
                return float(str(d).rstrip('s'))
            except Exception:
                return 0.0
        total_avg_power = sum(float(r.get("avg_power", 0.0)) for r in power_rails_data)
        total_energy_mJ = sum(float(r.get("total_power", 0.0)) for r in power_rails_data)
        global_duration_sec = max((_parse_duration(r.get("duration", "")) for r in power_rails_data), default=0.0)
        global_duration_str = f"{global_duration_sec:.6f}s" if global_duration_sec > 0 else "-"
        total_row_html = f'<tr><td>总计</td><td>{global_duration_str}</td><td>{total_avg_power:.3f}</td><td>{total_energy_mJ:.3f}</td></tr>'
        power_rails_rows = '\n'.join(
            [total_row_html] + [
                f'<tr><td>{row["label"]}</td><td>{row["duration"]}</td><td>{row["avg_power"]}</td><td>{row["total_power"]}</td></tr>'
                for row in power_rails_data
            ]
        )
        frequency_rows = '\n'.join([
            f'<tr><td>{row["label"]}</td><td>{row["avg_freq"]}</td><td>{row["max_freq"]}</td><td>{row["min_freq"]}</td></tr>'
            for row in frequency_data
        ])
        series_list_json = json.dumps([
            {
                "label": row["label"],
                "points": sorted(row["series_points"], key=lambda p: p.get("x", 0))
            } for row in power_rails_data if row.get("series_points")
        ], ensure_ascii=False)
        html_content = (
            html
            .replace('__BATTERY_ROWS__', battery_rows)
            .replace('__POWER_RAILS_ROWS__', power_rails_rows)
            .replace('__FREQUENCY_ROWS__', frequency_rows)
            .replace('__SERIES_LIST__', series_list_json)
        )
        with open("report/report.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("HTML报告已生成: report.html")


if __name__ == "__main__":
    Power_consumption_data_processing().run()


