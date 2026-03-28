/**
 * CF Pages Function: ASR WebSocket 代理
 *
 * 浏览器 WebSocket 无法设置 Authorization header，
 * 本 Function 作为代理，在服务端添加认证头后转发到 DashScope ASR。
 *
 * 路径: /api/asr  (自动映射自 functions/api/asr.js)
 * 环境变量: QWEN_API_KEY (在 CF Dashboard → Settings → Environment variables 中配置)
 */

const DASHSCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/";
const ASR_MODEL = "fun-asr-realtime";

export async function onRequest(context) {
  const upgradeHeader = context.request.headers.get("Upgrade");
  if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
    return new Response("Expected WebSocket upgrade", { status: 426 });
  }

  const apiKey = context.env.QWEN_API_KEY;
  if (!apiKey) {
    return new Response("QWEN_API_KEY not configured", { status: 500 });
  }

  // 1. 连接 DashScope WebSocket（带 Authorization header）
  let dashscopeResp;
  try {
    dashscopeResp = await fetch(DASHSCOPE_WS_URL, {
      headers: {
        Upgrade: "websocket",
        Authorization: `bearer ${apiKey}`,
      },
    });
  } catch (e) {
    return new Response(`Failed to connect to DashScope: ${e.message}`, {
      status: 502,
    });
  }

  const dashscopeWs = dashscopeResp.webSocket;
  if (!dashscopeWs) {
    return new Response("DashScope did not return a WebSocket", {
      status: 502,
    });
  }
  dashscopeWs.accept();

  // 2. 创建面向客户端的 WebSocket 对
  const pair = new WebSocketPair();
  const [clientWs, serverWs] = [pair[0], pair[1]];
  serverWs.accept();

  // 3. 生成任务 ID
  const taskId = crypto.randomUUID().replace(/-/g, "");

  // 4. 发送 run-task 启动 ASR
  dashscopeWs.send(
    JSON.stringify({
      header: {
        action: "run-task",
        task_id: taskId,
        streaming: "duplex",
      },
      payload: {
        task_group: "audio",
        task: "asr",
        function: "recognition",
        model: ASR_MODEL,
        parameters: { format: "pcm", sample_rate: 16000 },
        input: {},
      },
    }),
  );

  // 5. DashScope → 客户端：解析识别结果并转发
  dashscopeWs.addEventListener("message", (event) => {
    try {
      if (typeof event.data !== "string") return;
      const msg = JSON.parse(event.data);
      const evt = msg.header?.event || "";

      if (evt === "task-started") {
        serverWs.send(JSON.stringify({ type: "ready" }));
      } else if (evt === "result-generated") {
        const sentence = msg.payload?.output?.sentence || {};
        const text = sentence.text || "";
        const isEnd = sentence.sentence_end || false;
        if (text) {
          serverWs.send(
            JSON.stringify({ type: "result", text, is_end: isEnd }),
          );
        }
      } else if (evt === "task-finished") {
        serverWs.send(JSON.stringify({ type: "done" }));
        try {
          serverWs.close(1000, "done");
        } catch {}
      } else if (evt === "task-failed") {
        const errorMsg = msg.header?.error_message || "识别失败";
        serverWs.send(JSON.stringify({ type: "error", message: errorMsg }));
        try {
          serverWs.close(1000, "error");
        } catch {}
      }
    } catch {
      // ignore parse errors
    }
  });

  dashscopeWs.addEventListener("close", () => {
    try {
      serverWs.close(1000, "upstream closed");
    } catch {}
  });

  dashscopeWs.addEventListener("error", () => {
    try {
      serverWs.send(
        JSON.stringify({ type: "error", message: "ASR 服务连接异常" }),
      );
      serverWs.close(1011, "upstream error");
    } catch {}
  });

  // 6. 客户端 → DashScope：转发音频数据和控制命令
  serverWs.addEventListener("message", (event) => {
    try {
      if (event.data instanceof ArrayBuffer) {
        // 二进制音频数据 → 直接转发
        dashscopeWs.send(event.data);
      } else if (typeof event.data === "string") {
        const data = JSON.parse(event.data);
        if (data.action === "stop") {
          // 发送 finish-task
          dashscopeWs.send(
            JSON.stringify({
              header: {
                action: "finish-task",
                task_id: taskId,
                streaming: "duplex",
              },
              payload: { input: {} },
            }),
          );
        }
      }
    } catch {
      // ignore
    }
  });

  serverWs.addEventListener("close", () => {
    try {
      dashscopeWs.close();
    } catch {}
  });

  // 7. 返回客户端 WebSocket
  return new Response(null, { status: 101, webSocket: clientWs });
}
