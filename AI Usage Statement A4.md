# AI Usage Statement

## AI tool used
Claude (Anthropic), Chatgpt
## What the AI generated
| Area | Files | AI contribution |
|---|---|---|
| Streamlit app and instrumentation | `app.py`, `pipeline.py`, `captioner.py`, `metrics.py` | Drafted by Claude 
| Monitoring config | `prometheus.yml`, `alert_rules.yml`, `alertmanager.yml`, `alert_receiver.py`, `docker-compose.yml`, `grafana/provisioning/*` | Drafted by Claude |
| Grafana dashboard | `gen_dashboard.py`, `grafana/dashboards/captioning_dashboard.json` | Panel layout, styling choices (colour-blind-safe palette, axis labels, units, descriptions) and all PromQL queries were assisted by Claude |
| Test data and docs | `make_test_data.py`, `README.md`, `promql_notes.md`, `.gitignore` | Drafted by Claude |
| Troubleshooting | n/a | Claude diagnosed the disk-space failure (CUDA build of PyTorch), the repeated `torchvision` watcher warning, the misleading `spanNulls` lines in the dashboard |

## AI-generated PromQL and regex (Code of Conduct attribution)
All PromQL in the dashboard and in `alert_rules.yml`  was drafted by Claude. The comments in `alert_rules.yml` and `promql_notes.md` describe the intent of each query; the actual prompt that produced them is the initial prompt above. Regexes used:
- `mode=~"user|system|iowait"` (CPU-by-mode panel)
- `device!~"lo|veth.*|docker.*|br-.*"` (network panels)

## Verification of the AI's work
I worked through the calculations for the key queries (rate, histogram_quantile p95, Summary mean, error ratio, CPU utilisation) by hand using the examples in `promql_notes.md`
