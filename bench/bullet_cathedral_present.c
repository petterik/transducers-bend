// Native presentation for a CPU-rendered Bend Array<U32>. Metal only uploads
// and copies the finished BGRA pixels to the system window; it does not draw
// or simulate the scene.
#ifdef __OBJC__

#import <AppKit/AppKit.h>
#import <QuartzCore/QuartzCore.h>

#define CATHEDRAL_WIDTH 1920u
#define CATHEDRAL_HEIGHT 1080u
#define CATHEDRAL_PIXELS ((u64)CATHEDRAL_WIDTH * CATHEDRAL_HEIGHT)

static id<MTLDevice> cathedral_device;
static id<MTLCommandQueue> cathedral_queue;
static id<MTLTexture> cathedral_texture;
static u32* cathedral_staging;

static bool cathedral_pump(NSWindow* win) {
  for (;;) {
    NSEvent* event = [NSApp nextEventMatchingMask:NSEventMaskAny
      untilDate:NSDate.distantPast inMode:NSDefaultRunLoopMode dequeue:YES];
    if (event == nil) {
      break;
    }
    [NSApp sendEvent:event];
  }
  NSMutableData* events = [win.contentView valueForKey:@"evs"];
  const u32* words = events.bytes;
  bool open = true;
  for (u64 i = 0; i < events.length / (5 * sizeof(u32)); i += 1) {
    const u32* event = words + 5 * i;
    if (event[0] == 3 || (event[0] == 0 && event[1] == 27
      && event[2] != 0)) {
      open = false;
    }
  }
  events.length = 0;
  return open;
}

static void cathedral_prepare(id<MTLDevice> device) {
  if (cathedral_texture != nil && cathedral_device == device) {
    return;
  }
  cathedral_device = device;
  cathedral_queue = [device newCommandQueue];
  MTLTextureDescriptor* desc = [MTLTextureDescriptor
    texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
    width:CATHEDRAL_WIDTH height:CATHEDRAL_HEIGHT mipmapped:NO];
  desc.storageMode = MTLStorageModeShared;
  desc.usage = MTLTextureUsageShaderRead;
  cathedral_texture = [device newTextureWithDescriptor:desc];
  if (cathedral_queue == nil || cathedral_texture == nil) {
    err_fail("Bullet Cathedral: could not allocate the presentation texture");
  }
  if (cathedral_staging == NULL) {
    cathedral_staging = io_mem(malloc(CATHEDRAL_PIXELS * sizeof(u32)));
  }
}

static bool cathedral_present(Env e, intptr_t at, Term pixels) {
  NSWindow* win = (__bridge NSWindow*)(void*)at;
  if (!cathedral_pump(win)) {
    blk_free(e, pixels);
    return false;
  }
  if (term_tag(pixels) != TAG_BUF
    || (1ull << blk_cls(pixels)) < CATHEDRAL_PIXELS) {
    blk_free(e, pixels);
    err_fail("Bullet Cathedral: expected a packed 1920x1080 U32 array");
  }
  CAMetalLayer* layer = (CAMetalLayer*)win.contentView.layer;
  layer.drawableSize = CGSizeMake(CATHEDRAL_WIDTH, CATHEDRAL_HEIGHT);
  cathedral_prepare(layer.device);

  Loc loc = blk_loc(e.mem, pixels);
  for (u64 i = 0; i < CATHEDRAL_PIXELS; i += 1) {
    cathedral_staging[i] = (u32)blk_read(e.mem, false, loc, (u32)i)
      | 0xff000000u;
  }
  blk_free(e, pixels);

  @autoreleasepool {
    [cathedral_texture replaceRegion:MTLRegionMake2D(0, 0,
      CATHEDRAL_WIDTH, CATHEDRAL_HEIGHT) mipmapLevel:0
      withBytes:cathedral_staging bytesPerRow:CATHEDRAL_WIDTH * sizeof(u32)];
    id<CAMetalDrawable> drawable = [layer nextDrawable];
    if (drawable != nil) {
      id<MTLCommandBuffer> command = [cathedral_queue commandBuffer];
      id<MTLBlitCommandEncoder> blit = [command blitCommandEncoder];
      [blit copyFromTexture:cathedral_texture sourceSlice:0 sourceLevel:0
        sourceOrigin:MTLOriginMake(0, 0, 0)
        sourceSize:MTLSizeMake(CATHEDRAL_WIDTH, CATHEDRAL_HEIGHT, 1)
        toTexture:drawable.texture destinationSlice:0 destinationLevel:0
        destinationOrigin:MTLOriginMake(0, 0, 0)];
      [blit endEncoding];
      [command presentDrawable:drawable];
      [command commit];
      [command waitUntilCompleted];
      if (command.error != nil) {
        err_fail(command.error.localizedDescription.UTF8String);
      }
    }
  }
  return true;
}

#else

static bool cathedral_present(Env e, intptr_t at, Term pixels) {
  blk_free(e, pixels);
  err_fail("Bullet Cathedral's native presenter currently requires macOS");
  return false;
}

#endif

Term present_run(Env e, Term* f, IoWork* w) {
  bool open = cathedral_present(e, (intptr_t)io_hand_v(f[0]), f[1]);
  return io_tup(e, f[0], term_pak(open ? CID(True) : CID(False), 0));
}

static void __attribute__((constructor)) present_use(void) {
  io_eff(CID(present), present_run, 0);
}
