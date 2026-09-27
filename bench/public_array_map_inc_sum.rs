// Rust iterator and direct-loop controls for public_array_map_inc_sum.bend.
use std::time::Instant;

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
        values.iter().copied().map(|x| x.wrapping_add(1))
            .fold(0u32, u32::wrapping_add)
    } else {
        let mut sum = 0u32;
        for &value in &values {
            sum = sum.wrapping_add(value.wrapping_add(1));
        }
        sum
    };
    drop(values);
    let elapsed = before.elapsed().as_micros();
    println!("{elapsed} {answer}");
}
