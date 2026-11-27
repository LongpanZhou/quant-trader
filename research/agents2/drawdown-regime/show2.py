import json

r = json.load(open('research/agents2/drawdown-regime/result.json'))
names = ['winner', 'dd08_stop2', 'dd08_stop2_75', 'dd10_bil', 'dd05_bil', 'dd15_bil', 'dd05_half', 'dd08_qqq']
years = sorted(r['variants']['winner']['yearly'])
print('year  ' + '  '.join(f'{n[:12]:>12s}' for n in names) + '     TQQQ')
for y in years:
    row = f'{y}  '
    for n in names:
        row += f"{r['variants'][n]['yearly'][y]['strategy']*100:11.1f}%  "
    row += f"{r['variants']['winner']['yearly'][y]['benchmark']*100:8.1f}%"
    print(row)

print('\nyearly max DD on 1m marks (%)')
print('year  ' + '  '.join(f'{n[:12]:>12s}' for n in names))
for y in years:
    row = f'{y}  '
    for n in names:
        row += f"{r['variants'][n]['yearly_dd'][y]*100:11.1f}%  "
    print(row)

print('\nforward returns by dd bucket')
print(f"{'bucket':>10} {'n':>5} {'fwd5':>8} {'hit':>5} {'fwd20':>8} {'hit':>5} {'qqq20':>8}")
for b in r['forward_returns']:
    print(f"{b['bucket']:>10} {b['n']:5d} {b['fwd5']*100:7.2f}% {b['fwd5_hit']*100:4.0f}% "
          f"{b['fwd20']*100:7.2f}% {b['fwd20_hit']*100:4.0f}% {b['qqq20']*100:7.2f}%")

print('\nsignificance', r['significance'])
