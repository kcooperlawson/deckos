"""Deterministic preview data. Never probes or changes the host."""
from copy import deepcopy
from runners import ALL
from score import AI_MODEL, score


def snapshot():
    env = dict(cpu='AMD Ryzen 7 7800X3D', gpu='AMD Radeon RX 9070 XT', ram_gb=32,
               kernel='6.18.55-2-cachyos-lts', mesa='26.2.5', scheduler='lavd',
               power_profile='performance', governor='performance', deckos='0.14.2')
    # A full DecKoOS Score run's measurements on a PC like the reference machine
    specs = [('cpu-7z', 'multi', 'All cores (total)', 'MIPS', 108420, True),
             ('cpu-7z', 'single', 'One core (total)', 'MIPS', 7820, True),
             ('memory', 'triad', 'Bandwidth (triad)', 'GB/s', 45.8, True),
             ('memory', 'latency', 'Latency', 'ns', 70.6, False),
             ('disk', 'seq_read', 'Sequential read', 'MB/s', 6320, True),
             ('disk', 'seq_write', 'Sequential write', 'MB/s', 5110, True),
             ('disk', 'rand_read', 'Random 4K read (QD32)', 'IOPS', 815000, True),
             ('disk', 'rand_write', 'Random 4K write (QD32)', 'IOPS', 604000, True),
             ('disk', 'rand_read_qd1', 'Random 4K read (QD1, how snappy it feels)', 'IOPS', 18400, True),
             ('gpu-vkmark', 'score', 'vkmark score', 'points', 15840, True),
             ('ai-ollama', 'generate', f'Writing ({AI_MODEL})', 'tokens/s', 318, True),
             ('ai-ollama', 'prompt', f'Reading the prompt ({AI_MODEL})', 'tokens/s', 6150, True)]
    runs = []
    labels = ['First score', 'Fresh boot', 'Gaming profile', 'Driver update', 'Evening check', 'Tuned baseline']
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
        run = dict(version=1, id=f'demo-{i}', label=name, started=1792836000 - (5-i)*86400,
                   seconds=690 + i * 13, repeat=3, kind='score', status='complete',
                   environment=deepcopy(env), results=list(results.values()))
        run['score'] = score(run)
        runs.append(run)
    return runs, env, {key: dict(available=True, reason='') for key in ALL}
