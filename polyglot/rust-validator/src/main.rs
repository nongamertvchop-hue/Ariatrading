use std::io::{self, BufRead};

fn parse(row: &str) -> Result<(i64, f64, f64, f64, f64, Option<f64>), String> {
    let p: Vec<&str> = row.trim().split('\t').collect();
    if !(5..=6).contains(&p.len()) { return Err("expected 5 or 6 tab-separated fields".into()); }
    let time = p[0].parse::<i64>().map_err(|_| "invalid time")?;
    if time <= 0 { return Err("invalid time".into()); }
    let open = p[1].parse::<f64>().map_err(|_| "invalid price")?;
    let high = p[2].parse::<f64>().map_err(|_| "invalid price")?;
    let low = p[3].parse::<f64>().map_err(|_| "invalid price")?;
    let close = p[4].parse::<f64>().map_err(|_| "invalid price")?;
    if ![open, high, low, close].iter().all(|v| v.is_finite() && *v > 0.0) { return Err("prices must be finite and positive".into()); }
    if high < open || high < close || low > open || low > close || low > high { return Err("invalid candle geometry".into()); }
    let volume = if p.len() == 6 { let v = p[5].parse::<f64>().map_err(|_| "invalid volume")?; if !v.is_finite() || v < 0.0 { return Err("invalid volume".into()); } Some(v) } else { None };
    Ok((time, open, high, low, close, volume))
}

fn main() {
    let stdin = io::stdin();
    let mut previous = 0i64;
    for (index, line) in stdin.lock().lines().enumerate() {
        let line = match line { Ok(v) => v, Err(e) => { eprintln!("stdin: {e}"); break; } };
        if line.trim().is_empty() { continue; }
        match parse(&line) {
            Ok((time, open, high, low, close, volume)) if time > previous => {
                previous = time;
                match volume { Some(v) => println!(r#"{{"ok":true,"index":{},"time":{},"open":{},"high":{},"low":{},"close":{},"volume":{}}}"#, index, time, open, high, low, close, v), None => println!(r#"{{"ok":true,"index":{},"time":{},"open":{},"high":{},"low":{},"close":{}}}"#, index, time, open, high, low, close) }
            }
            Ok(_) => println!(r#"{{"ok":false,"index":{},"error":"timestamp must be strictly increasing"}}"#, index),
            Err(error) => println!(r#"{{"ok":false,"index":{},"error":"{}"}}"#, index, error),
        }
    }
}
