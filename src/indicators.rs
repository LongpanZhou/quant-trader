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
}
