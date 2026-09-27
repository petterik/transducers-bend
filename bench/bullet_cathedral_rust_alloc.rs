// Separate allocation meter for the Rust control; excluded from scene LOC.
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

pub mod alloc_meter {
    use super::*;
    static ACTIVE: AtomicBool = AtomicBool::new(false);
    static COUNT: AtomicUsize = AtomicUsize::new(0);

    pub struct Meter;
    unsafe impl GlobalAlloc for Meter {
        unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
            if ACTIVE.load(Ordering::Relaxed) { COUNT.fetch_add(1, Ordering::Relaxed); }
            unsafe { System.alloc(layout) }
        }
        unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
            if ACTIVE.load(Ordering::Relaxed) { COUNT.fetch_add(1, Ordering::Relaxed); }
            unsafe { System.alloc_zeroed(layout) }
        }
        unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
            if ACTIVE.load(Ordering::Relaxed) { COUNT.fetch_add(1, Ordering::Relaxed); }
            unsafe { System.realloc(ptr, layout, new_size) }
        }
        unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
            unsafe { System.dealloc(ptr, layout) }
        }
    }
    pub fn start() {
        COUNT.store(0, Ordering::Relaxed);
        ACTIVE.store(true, Ordering::Relaxed);
    }
    pub fn stop() -> usize {
        ACTIVE.store(false, Ordering::Relaxed);
        COUNT.load(Ordering::Relaxed)
    }
}

#[global_allocator]
static GLOBAL: alloc_meter::Meter = alloc_meter::Meter;

#[path = "bullet_cathedral_control.rs"]
mod scene;

fn main() { scene::main(); }
