/// Simple moving average of the last `n` values.
pub fn sma(values: &[f64], n: usize) -> Option<f64> {
    if n == 0 || values.len() < n {
        return None;
    }
    Some(values[values.len() - n..].iter().sum::<f64>() / n as f64)
}

/// Population standard deviation of the last `n` values.
pub fn stddev(values: &[f64], n: usize) -> Option<f64> {
    let mean = sma(values, n)?;
    let var = values[values.len() - n..].iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
    Some(var.sqrt())
}

/// Least-squares fit of `y` against 0,1,2,... Returns (slope, R-squared).
pub fn linreg(y: &[f64]) -> Option<(f64, f64)> {
    let n = y.len() as f64;
    if y.len() < 3 {
        return None;
    }
    let mx = (n - 1.0) / 2.0;
    let my = y.iter().sum::<f64>() / n;
    let (mut sxy, mut sxx, mut syy) = (0.0, 0.0, 0.0);
    for (i, v) in y.iter().enumerate() {
        let dx = i as f64 - mx;
        sxy += dx * (v - my);
        sxx += dx * dx;
        syy += (v - my).powi(2);
    }
    if syy == 0.0 {
        return Some((0.0, 0.0));
    }
    Some((sxy / sxx, sxy * sxy / (sxx * syy)))
}

/// Wilder's RSI over the whole series, returning the latest value (0..=100).
pub fn rsi(values: &[f64], period: usize) -> Option<f64> {
    if period == 0 || values.len() < period + 1 {
        return None;
    }
    let (mut gain, mut loss) = (0.0, 0.0);
    for w in values[..=period].windows(2) {
        let d = w[1] - w[0];
        if d > 0.0 {
            gain += d;
        } else {
            loss -= d;
        }
    }
    gain /= period as f64;
    loss /= period as f64;
    let p = period as f64;
    for w in values[period..].windows(2) {
        let d = w[1] - w[0];
        gain = (gain * (p - 1.0) + d.max(0.0)) / p;
        loss = (loss * (p - 1.0) + (-d).max(0.0)) / p;
    }
    if loss == 0.0 {
        return Some(if gain == 0.0 { 50.0 } else { 100.0 });
    }
    Some(100.0 - 100.0 / (1.0 + gain / loss))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sma_basic() {
        assert_eq!(sma(&[1.0, 2.0, 3.0, 4.0], 2), Some(3.5));
        assert_eq!(sma(&[1.0], 2), None);
    }

    #[test]
    fn stddev_basic() {
        assert_eq!(stddev(&[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], 8), Some(2.0));
    }

    #[test]
    fn linreg_perfect_line() {
        let (slope, r2) = linreg(&[1.0, 3.0, 5.0, 7.0]).unwrap();
        assert!((slope - 2.0).abs() < 1e-12 && (r2 - 1.0).abs() < 1e-12);
    }

    #[test]
    fn rsi_extremes() {
        let up: Vec<f64> = (0..30).map(|i| i as f64).collect();
        let down: Vec<f64> = (0..30).map(|i| 100.0 - i as f64).collect();
        assert_eq!(rsi(&up, 14), Some(100.0));
        assert!(rsi(&down, 14).unwrap() < 1e-9);
        assert_eq!(rsi(&[1.0, 2.0], 14), None);
    }

    #[test]
    fn rsi_balanced_is_50() {
        let v: Vec<f64> = (0..41).map(|i| if i % 2 == 0 { 10.0 } else { 11.0 }).collect();
        let r = rsi(&v, 14).unwrap();
        assert!((r - 50.0).abs() < 5.0, "rsi was {r}");
    }
}
