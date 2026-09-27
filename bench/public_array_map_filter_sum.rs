// Rust controls for public_array_map_filter_sum.bend.
use std::time::Instant;

fn transform(x: u32) -> u32 {
    let a = x.wrapping_mul(2_654_435_761);
    let b = a ^ (a >> 16);
    let c = b.wrapping_mul(2_246_822_507);
    c ^ (c >> 13)
}

fn main() {
    let mut args = std::env::args().skip(1);
    let mode: u8 = args.next().unwrap().parse().unwrap();
    let depth: u32 = args.next().unwrap().parse().unwrap();
    let seed: u32 = args.next().unwrap().parse().unwrap();
    assert!(mode < 2 && depth <= 23 && args.next().is_none());
    let count = 1usize << depth;
    let values: Vec<u32> = (0..count)
        .map(|i| (i as u32).wrapping_mul(1_664_525).wrapping_add(seed))
        .collect();

    let before = Instant::now();
    let answer = if mode == 0 {
        values.iter().copied().map(transform)
            .filter(|value| value & 255 < 96)
            .fold(0u32, u32::wrapping_add)
    } else {
        let mut sum = 0u32;
        for &value in &values {
            let mapped = transform(value);
            if mapped & 255 < 96 {
                sum = sum.wrapping_add(mapped);
            }
        }
        sum
    };
    drop(values);
    let elapsed = before.elapsed().as_micros();
    println!("{elapsed} {answer}");
}
