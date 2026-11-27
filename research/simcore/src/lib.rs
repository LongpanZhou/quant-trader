//! Compiled version of `research/bt.py::simulate`.
//!
//! Same rules, same order of operations, line for line:
//! weights[i] (set at bar i's close) are executed at bar i+1's open; sells
//! first, then buys; a resize happens only when it is more than `band` of
//! book equity away from target; exits and new entries always trade;
//! slippage is charged on traded notional.
//!
//! All arrays are row-major, contiguous f64. `simcore_simulate_many` runs
//! `m` weight matrices over the same prices on `threads` OS threads.

use std::slice;

struct Out<'a> {
    equity: &'a mut [f64],
    cash: &'a mut [f64],
}

#[allow(clippy::too_many_arguments)]
fn run_one(
    n: usize,
    k: usize,
    opens: &[f64],
    closes: &[f64],
    weights: &[f64],
    band: f64,
    slip: f64,
    start_equity: f64,
    out: Out,
) -> (i64, f64) {
    let mut cash = start_equity;
    let mut shares = vec![0.0f64; k];
    let mut fills: i64 = 0;
    let mut traded = 0.0f64;

    if n == 0 {
        return (0, 0.0);
    }
    out.equity[0] = start_equity;
    out.cash[0] = cash;

    for i in 0..n - 1 {
        let bar = i + 1;
        let px = &opens[bar * k..bar * k + k];
        let target = &weights[i * k..i * k + k];

        let mut book = cash;
        for s in 0..k {
            book += shares[s] * px[s];
        }
        if book > 0.0 {
            // Sell side / exits first.
            for s in 0..k {
                if shares[s] <= 0.0 {
                    continue;
                }
                let mut qty;
                if target[s] == 0.0 {
                    qty = shares[s];
                } else {
                    let excess = shares[s] * px[s] - target[s] * book;
                    if excess <= band * book {
                        continue;
                    }
                    qty = excess / px[s];
                }
                if qty > shares[s] {
                    qty = shares[s];
                }
                if qty <= 0.0 {
                    continue;
                }
                let price = px[s] * (1.0 - slip);
                let notional = qty * price;
                cash += notional;
                traded += notional;
                fills += 1;
                shares[s] -= qty;
                if shares[s] < 1e-10 {
                    shares[s] = 0.0;
                }
            }
            // Buy side / resizes.
            for s in 0..k {
                if target[s] <= 0.0 {
                    continue;
                }
                let current = shares[s] * px[s];
                let shortfall = target[s] * book - current;
                let is_new = shares[s] <= 0.0;
                if !is_new && shortfall <= band * book {
                    continue;
                }
                if shortfall <= 0.0 {
                    continue;
                }
                let price = px[s] * (1.0 + slip);
                let qty = (shortfall / price).min(cash / price);
                if qty <= 1e-12 {
                    continue;
                }
                let notional = qty * price;
                cash -= notional;
                traded += notional;
                fills += 1;
                shares[s] += qty;
            }
        }
        let cl = &closes[bar * k..bar * k + k];
        let mut eq = cash;
        for s in 0..k {
            eq += shares[s] * cl[s];
        }
        out.equity[bar] = eq;
        out.cash[bar] = cash;
    }
    (fills, traded)
}

/// One simulation. Returns 0 on success.
///
/// # Safety
/// Pointers must reference contiguous f64 arrays of the stated sizes:
/// opens/closes/weights n*k, equity_out/cash_out n.
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn simcore_simulate(
    n: usize,
    k: usize,
    opens: *const f64,
    closes: *const f64,
    weights: *const f64,
    band: f64,
    slip: f64,
    start_equity: f64,
    equity_out: *mut f64,
    cash_out: *mut f64,
    fills_out: *mut i64,
    traded_out: *mut f64,
) -> i32 {
    if opens.is_null() || closes.is_null() || weights.is_null() || equity_out.is_null() {
        return 1;
    }
    let opens = slice::from_raw_parts(opens, n * k);
    let closes = slice::from_raw_parts(closes, n * k);
    let weights = slice::from_raw_parts(weights, n * k);
    let out = Out {
        equity: slice::from_raw_parts_mut(equity_out, n),
        cash: slice::from_raw_parts_mut(cash_out, n),
    };
    let (f, t) = run_one(n, k, opens, closes, weights, band, slip, start_equity, out);
    *fills_out = f;
    *traded_out = t;
    0
}

/// `m` simulations over the same prices, split across `threads` threads.
///
/// # Safety
/// weights m*n*k; equity_out/cash_out m*n; fills_out/traded_out m.
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn simcore_simulate_many(
    m: usize,
    n: usize,
    k: usize,
    opens: *const f64,
    closes: *const f64,
    weights: *const f64,
    band: f64,
    slip: f64,
    start_equity: f64,
    equity_out: *mut f64,
    cash_out: *mut f64,
    fills_out: *mut i64,
    traded_out: *mut f64,
    threads: usize,
) -> i32 {
    if opens.is_null() || closes.is_null() || weights.is_null() || equity_out.is_null() {
        return 1;
    }
    let opens = slice::from_raw_parts(opens, n * k);
    let closes = slice::from_raw_parts(closes, n * k);
    let weights = slice::from_raw_parts(weights, m * n * k);
    let equity = slice::from_raw_parts_mut(equity_out, m * n);
    let cash = slice::from_raw_parts_mut(cash_out, m * n);
    let fills = slice::from_raw_parts_mut(fills_out, m);
    let traded = slice::from_raw_parts_mut(traded_out, m);

    let threads = threads.max(1).min(m.max(1));
    let per = m.div_ceil(threads);
    std::thread::scope(|scope| {
        let mut eq_rest = &mut equity[..];
        let mut cash_rest = &mut cash[..];
        let mut f_rest = &mut fills[..];
        let mut t_rest = &mut traded[..];
        let mut first = 0usize;
        while first < m {
            let cnt = per.min(m - first);
            let (eq_chunk, e2) = eq_rest.split_at_mut(cnt * n);
            let (cash_chunk, c2) = cash_rest.split_at_mut(cnt * n);
            let (f_chunk, f2) = f_rest.split_at_mut(cnt);
            let (t_chunk, t2) = t_rest.split_at_mut(cnt);
            eq_rest = e2;
            cash_rest = c2;
            f_rest = f2;
            t_rest = t2;
            let w = &weights[first * n * k..(first + cnt) * n * k];
            scope.spawn(move || {
                for j in 0..cnt {
                    let out = Out {
                        equity: &mut eq_chunk[j * n..(j + 1) * n],
                        cash: &mut cash_chunk[j * n..(j + 1) * n],
                    };
                    let (f, t) = run_one(
                        n,
                        k,
                        opens,
                        closes,
                        &w[j * n * k..(j + 1) * n * k],
                        band,
                        slip,
                        start_equity,
                        out,
                    );
                    f_chunk[j] = f;
                    t_chunk[j] = t;
                }
            });
            first += cnt;
        }
    });
    0
}
