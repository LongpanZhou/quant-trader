import {
  runCustomBacktest,
  type CustomWorkerRequest,
  type CustomWorkerResponse,
} from "@/lib/custom-engine";

// The page creates this module as a real Web Worker. Keeping the execution
// here means a slow or infinite decide(ctx) can be terminated by the page
// without freezing the UI, and the user's code never leaves the browser.

type WorkerScope = {
  onmessage: ((event: MessageEvent<CustomWorkerRequest>) => void) | null;
  postMessage: (message: CustomWorkerResponse) => void;
};

const scope = self as unknown as WorkerScope;

scope.onmessage = (event: MessageEvent<CustomWorkerRequest>) => {
  const request = event.data;
  if (!request || request.type !== "run") return;
  try {
    const result = runCustomBacktest(request.input);
    scope.postMessage({ type: "done", result });
  } catch (error) {
    scope.postMessage({
      type: "error",
      error: error instanceof Error ? error.message : String(error),
    });
  }
};
