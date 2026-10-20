"""Retry only transient reads; capture broadcast acknowledgements immediately."""
import time


def guarded_request(request, method, params, *, broadcast, transient, sleep=time.sleep):
    for attempt in range(3):
        try:
            response = request(method, params)
        except Exception as error:
            retryable = any(fragment in str(error).lower() for fragment in
                            ("502", "503", "504", "429", "timed out", "connection", "invalid json"))
            # A write may already have reached the server even without an ack.
            if method == "eth_sendRawTransaction" or not retryable or attempt == 2:
                raise
            transient(method, attempt + 1, str(error)[:240])
            sleep(5)
            continue
        if method == "eth_sendRawTransaction" and response.get("result"):
            broadcast(response["result"])
        return response
