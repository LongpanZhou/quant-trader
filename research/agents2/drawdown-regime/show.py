import json

r = json.load(open('research/agents2/drawdown-regime/result.json'))
W = r['variants']['winner']['costs']['1bp']
print('winner 1bp 10y', round(W['10y']['cagr']*100, 2), round(W['10y']['max_drawdown']*100, 2),
      '5y', round(W['5y']['cagr']*100, 2), round(W['5y']['max_drawdown']*100, 2))
for name, e in r['variants'].items():
    print()
    print('==' + name, '|', e['rules'])
    if 'stop_events' in e:
        print('   stop events', e['stop_events'])
    for bp in ('1bp', '5bp', '10bp'):
        c = e['costs'][bp]
        p = e['pass'][bp]
        a, b = c['10y'], c['5y']
        print('  %4s 10y %6.2f/%5.2f Sh%4.2f f%4d turn%7.1f | 5y %6.2f/%5.2f Sh%4.2f f%4d turn%7.1f | dom=%s dd2pp=%s tqqq=%s' % (
            bp, a['cagr']*100, a['max_drawdown']*100, a['sharpe'], a['fills'], a['turnover'],
            b['cagr']*100, b['max_drawdown']*100, b['sharpe'], b['fills'], b['turnover'],
            p['strict_dominance_vs_winner'], p['lower_dd_and_cagr_within_2pp'], p['beat_tqqq']))
    a = e['costs']['1bp']['10y']; b = e['costs']['1bp']['5y']
    print('  dd 10y', a['dd_peak'][:10], '->', a['dd_trough'][:10],
          '| 5y', b['dd_peak'][:10], '->', b['dd_trough'][:10])
    print('  exposure 10y %.1f%%  5y %.1f%%' % (a['exposure']*100, b['exposure']*100))
    if 'rolling3y' in e:
        q = e['rolling3y']
        print('  rolling3y n=%d beat TQQQ %d median %.1f%% worst DD %.1f%%' % (
            q['n'], q['beat_tqqq_cagr_and_dd'], q['median_cagr']*100, q['worst_dd']*100))
