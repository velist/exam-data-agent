import { describe, expect, it, vi, afterEach } from "vitest";
import { streamChat, StreamChatError } from "./api";

function createStream(chunks: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("streamChat", () => {
  it("parses multi-chunk sse frames in order", async () => {
    const events: Array<{ type: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: createStream([
          'data: {"type":"status","stage":"understanding","text":"正在理解问题..."}\n\n',
          'data: {"type":"table","columns":["x"],"rows":[["1"]]}\n\n',
          'data: {"type":"answer_chunk","text":"ok"}\n\n',
          'data: {"type":"done"}\n\n',
        ]),
      }),
    );

    await streamChat("test", [], { onEvent: (e) => events.push(e) });

    expect(events.map((e) => e.type)).toEqual(["status", "table", "answer_chunk", "done"]);
  });

  it("marks failures before first event as downgradeable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 502, body: null }),
    );

    await expect(streamChat("test", [], { onEvent: vi.fn() })).rejects.toMatchObject({
      beforeFirstEvent: true,
      code: "STREAM_INIT_FAILED",
    });
  });

  it("throws STREAM_INTERRUPTED when stream ends without terminal event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: createStream([
          'data: {"type":"status","stage":"understanding","text":"..."}\n\n',
          'data: {"type":"answer_chunk","text":"partial"}\n\n',
          // no done or error
        ]),
      }),
    );

    await expect(streamChat("test", [], { onEvent: vi.fn() })).rejects.toMatchObject({
      beforeFirstEvent: false,
      code: "STREAM_INTERRUPTED",
    });
  });

  it("does not throw when stream contains error event as terminal", async () => {
    const events: Array<{ type: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: createStream([
          'data: {"type":"error","code":"SQL_FAILED","message":"fail"}\n\n',
        ]),
      }),
    );

    await streamChat("test", [], { onEvent: (e) => events.push(e) });
    expect(events[0].type).toBe("error");
  });

  it("marks abort as isAbort", async () => {
    const controller = new AbortController();
    controller.abort();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")),
    );

    await expect(
      streamChat("test", [], { onEvent: vi.fn() }, { signal: controller.signal }),
    ).rejects.toMatchObject({
      isAbort: true,
      beforeFirstEvent: true,
    });
  });
});
