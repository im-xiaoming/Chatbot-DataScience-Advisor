# DataPath frontend

From the project root, run:

```bash
python -m http.server 5500 --directory frontend
```

Open `http://localhost:5500` for a standalone UI demo. Registration, login, and chat responses are simulated in this mode. The password is not saved; only the display name is kept in `sessionStorage` for the current tab.

After starting the FastAPI server described in [api/README.md](../api/README.md), open `http://localhost:5500/?api=http://localhost:8000`. Registration and login then use the PostgreSQL-backed API, and the chat response arrives as an actual HTTP stream. The text is still simulated on the server until RAG and the LLM are connected.

The frontend expects `POST /chat/stream` with `{"message":"..."}` and JSON events in `text/event-stream` format:

```text
data: {"type":"text","content":"Xin chào "}

data: {"type":"sources","sources":[{"title":"Nguồn","url":"https://example.com"}]}

data: {"type":"done"}

```

The API may also send `{"type":"error","message":"..."}`. Browser requests include the signed session cookie using `credentials: "include"`.
