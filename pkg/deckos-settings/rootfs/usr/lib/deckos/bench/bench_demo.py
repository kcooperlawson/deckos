"""Deterministic preview data. Never probes or changes the host."""
from copy import deepcopy
from runners import ALL


def snapshot():
    env = dict(cpu='AMD Ryzen 7 7800X3D', gpu='AMD Radeon RX 9070 XT', ram_gb=32,
               kernel='6.18.55-2-cachyos-lts', mesa='26.2.5', scheduler='lavd',
               power_profile='performance', governor='performance', deckos='0.3.16')
    specs = [('cpu-7z', 'multi', 'All cores (total)', 'MIPS', 108420, True),
             ('memory', 'triad', 'Bandwidth (triad)', 'GB/s', 45.8, True),
             ('memory', 'latency', 'Latency', 'ns', 70.6, False),
             ('disk', 'seq_read', 'Sequential read', 'MB/s', 6320, True),
             ('gpu-vkmark', 'score', 'vkmark score', 'points', 15840, True),
             ('ai-ollama', 'generate', 'Writing (gpt-oss:20b)', 'tokens/s', 113.8, True)]
    runs = []
    labels = ['First baseline', 'Fresh boot', 'Gaming profile', 'Driver update', 'Evening check', 'Tuned baseline']
    for i, name in enumerate(labels):
        results = {}
        for key, metric, title, unit, value, higher in specs:
            cls = ALL[key]
            result = results.setdefault(key, dict(runner=key, title=cls.title, group=cls.group,
                                                  metrics={}, error='', notes=[], seconds=65,
                                                  sensors={'cpu_temp': {'avg': 62.1, 'max': 74.3}},
                                                  trace={'cpu_temp': [49, 55, 61, 65, 64, 70, 74, 69, 63]}))
            value *= (0.89 + i * .022) if higher else (1.08 - i * .016)
            result['metrics'][metric] = dict(key=metric, name=title, unit=unit, higher_better=higher,
                                             values=[value * .995, value * 1.005, value])
        runs.append(dict(version=1, id=f'demo-{i}', label=name, started=1792836000 - (5-i)*86400,
                         seconds=410 + i * 13, repeat=3, kind='system', status='complete',
                         environment=deepcopy(env), results=list(results.values())))
    return runs, env, {key: dict(available=True, reason='') for key in ALL}
