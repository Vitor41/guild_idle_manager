# ML-054 portal spawn policy simulation

Policy: `portal-spawn-v1`. Generated: 2026-11-24T20:11:04.847450+00:00.

Runs: 64 deterministic seeds × 5 regions × 180 days × 4 stage levels × 2 Explorer bonus cases.

## Results

| Stage | Eligible bosses | Explorer bonus | Rolls / region / 180d | Portals / region / 180d | Median first portal (days, censored at 180) | Median interval (days) | No portal by 30 / 90 / 180d | Simultaneous portal cycles | Entry window missed* |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 pp | 520.084 | 66.828 | 1.75 | 2.5 | 0.0% / 0.0% / 0.0% | 18.46% (max 4) | 50.04%
| 1 | 1 | 5 pp | 478.238 | 80.822 | 1.25 | 2.0 | 0.0% / 0.0% / 0.0% | 22.38% (max 4) | 49.7%
| 15 | 1 | 0 pp | 520.041 | 66.85 | 1.75 | 2.5 | 0.0% / 0.0% / 0.0% | 18.89% (max 4) | 49.57%
| 15 | 1 | 5 pp | 479.894 | 80.259 | 1.25 | 2.0 | 0.0% / 0.0% / 0.0% | 22.18% (max 5) | 49.76%
| 30 | 2 | 0 pp | 520.847 | 66.569 | 1.62 | 2.5 | 0.0% / 0.0% / 0.0% | 18.45% (max 4) | 49.97%
| 30 | 2 | 5 pp | 478.363 | 80.759 | 1.0 | 2.0 | 0.0% / 0.0% / 0.0% | 22.03% (max 4) | 49.95%
| 50 | 4 | 0 pp | 520.519 | 66.644 | 1.5 | 2.5 | 0.0% / 0.0% / 0.0% | 18.36% (max 5) | 50.47%
| 50 | 4 | 5 pp | 478.256 | 80.797 | 1.25 | 2.0 | 0.0% / 0.0% / 0.0% | 22.76% (max 5) | 49.92%

## Chance and regional distribution

Each chance-distribution value is the share of eligible rolls at that effective chance.

| Stage | Eligible bosses | Explorer bonus | Effective chance distribution | Home-region share | Other-region share | Blocked cycles (no RNG) |
|---:|---:|---:|---|---:|---:|---|
| 1 | 1 | 0 pp | 8%: 12.97%, 9%: 11.92%, 10%: 10.84%, 11%: 9.76%, 12%: 8.63%, 13%: 7.61%, 14%: 6.66%, 15%: 5.71%, 16%: 4.85%, 17%: 4.07%, 18%: 3.38%, 19%: 2.73%, 20%: 10.87% | 19.74% | 80.26% | {'active_portal': 21353, 'content_unavailable': 0, 'cooldown': 42620}
| 1 | 1 | 5 pp | 13%: 17.01%, 14%: 14.8%, 15%: 12.73%, 16%: 10.81%, 17%: 9.02%, 18%: 7.5%, 19%: 6.13%, 20%: 4.97%, 21%: 3.98%, 22%: 3.16%, 23%: 2.43%, 24%: 1.86%, 25%: 5.59% | 20.06% | 79.94% | {'active_portal': 25831, 'content_unavailable': 0, 'cooldown': 51533}
| 15 | 1 | 0 pp | 8%: 12.97%, 9%: 11.89%, 10%: 10.81%, 11%: 9.72%, 12%: 8.66%, 13%: 7.63%, 14%: 6.64%, 15%: 5.73%, 16%: 4.84%, 17%: 4.02%, 18%: 3.32%, 19%: 2.72%, 20%: 11.04% | 19.76% | 80.24% | {'active_portal': 21358, 'content_unavailable': 0, 'cooldown': 42629}
| 15 | 1 | 5 pp | 13%: 16.84%, 14%: 14.71%, 15%: 12.66%, 16%: 10.75%, 17%: 8.98%, 18%: 7.47%, 19%: 6.13%, 20%: 4.98%, 21%: 4.0%, 22%: 3.2%, 23%: 2.48%, 24%: 1.92%, 25%: 5.89% | 19.99% | 80.01% | {'active_portal': 25649, 'content_unavailable': 0, 'cooldown': 51185}
| 30 | 2 | 0 pp | 8%: 12.9%, 9%: 11.87%, 10%: 10.76%, 11%: 9.7%, 12%: 8.65%, 13%: 7.62%, 14%: 6.63%, 15%: 5.72%, 16%: 4.84%, 17%: 4.08%, 18%: 3.39%, 19%: 2.74%, 20%: 11.11% | 19.98% | 80.02% | {'active_portal': 21278, 'content_unavailable': 0, 'cooldown': 42451}
| 30 | 2 | 5 pp | 13%: 17.0%, 14%: 14.83%, 15%: 12.74%, 16%: 10.78%, 17%: 9.04%, 18%: 7.52%, 19%: 6.14%, 20%: 4.95%, 21%: 3.93%, 22%: 3.11%, 23%: 2.42%, 24%: 1.86%, 25%: 5.69% | 19.97% | 80.03% | {'active_portal': 25817, 'content_unavailable': 0, 'cooldown': 51507}
| 50 | 4 | 0 pp | 8%: 12.94%, 9%: 11.88%, 10%: 10.81%, 11%: 9.72%, 12%: 8.61%, 13%: 7.6%, 14%: 6.58%, 15%: 5.65%, 16%: 4.78%, 17%: 4.02%, 18%: 3.35%, 19%: 2.75%, 20%: 11.31% | 19.85% | 80.15% | {'active_portal': 21300, 'content_unavailable': 0, 'cooldown': 42534}
| 50 | 4 | 5 pp | 13%: 17.01%, 14%: 14.81%, 15%: 12.74%, 16%: 10.8%, 17%: 9.06%, 18%: 7.49%, 19%: 6.13%, 20%: 4.95%, 21%: 3.95%, 22%: 3.1%, 23%: 2.42%, 24%: 1.86%, 25%: 5.68% | 20.11% | 79.89% | {'active_portal': 25823, 'content_unavailable': 0, 'cooldown': 51535}

*The missed-window estimate assumes player availability only from 20:00–22:00 UTC daily. Portal generation continues offline and the approved 12-hour entry deadline continues offline. This is a narrow availability scenario, not an estimate of the player's actual schedule.

The service helper found {1: 1, 15: 1, 30: 2, 50: 4} active boss/loot candidate counts by player level in a disposable catalog seeded from committed content. Region 1 (Vale da Fronteira) is labeled home, and the remaining four as other regions for reporting only. Every blocked cycle is counted before RNG; no-content stages never roll or accumulate failures. Null-marker legacy cycles are excluded from this new-policy simulation and covered separately by regression tests. The study does not model CPU participation, combat, rewards, rebellion rules, or real user behavior.

Parameters: base 8%, +1 pp per eligible failure, base cap 20%, Explorers cap +5 pp, 24h cooldown, 12h entry window. Total runtime: 22.919s.

Source revision: `4999670d79ec08d8573702a19e80eea5020a1e6e`. Selected source worktree: `clean`. SHA-256 values are in the JSON. The checkpoint file preserves completed case aggregates.
