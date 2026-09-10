# WalletSync frontend

React 19, strict TypeScript, and Vite 8, served by the existing Flask backend.
The interface uses custom responsive CSS, Lucide icons, bundled DM Sans and
DM Serif Display fonts, and react-markdown without raw HTML or remote images.
User messages render as plain text.

## Run

From the repository root, install Python dependencies into your virtual
environment using `pip install -r requirements.txt`. Node.js 22.12+ or 24+
is required for the frontend.

```sh
npm --prefix frontend ci
npm --prefix frontend run build
python src/web/app.py
```

Open http://127.0.0.1:5000. Build output lives in `src/web/static/app` and is
ignored by Git. Build the frontend before starting Flask on a fresh checkout.

For development, keep Flask running in one terminal and run
`npm --prefix frontend run dev` in another. Open the Vite URL printed in the
terminal, including `/static/app/`. API and image requests proxy to Flask.

## Check

```sh
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run test:e2e
python -m pytest tests/test_web.py tests/test_agent_scope.py tests/test_agent.py tests/test_matcher.py -q
```

The browser suite builds the app and starts an isolated Flask server on port
5055. It tests real local card matching and mocks assistant responses, so it
makes no AWS requests. Set `PYTHON` if your Python executable is outside the
repository's `venv`. The tests cover input safety, conversation history,
request races, reset, retry, responsive layouts, and automated accessibility.
Screenshots and failure traces are written to `frontend/test-results`.
Automated accessibility checks supplement manual visual and keyboard checks.

## Behavior

- Live matching debounces input by 350ms. Abort controllers and revision
  checks prevent old responses from overwriting a newer draft or chat result.
- Sending disables the composer until completion. Enter sends, Shift+Enter
  inserts a line break, and input method composition does not submit.
- Clearing a draft restores the most recent conversation's card matches.
- New chat aborts pending browser requests and clears local conversation
  state. An already running backend request may still finish.
- Agent failures preserve local matches and expose a retry action. Errors
  are not added to assistant history. Requests time out after 90 seconds.
- Fees and reward caps come from the local catalog. Ranking scores are not
  percentages or estimates of cash savings.
- The comparison shortlist places a focus-bank candidate first, followed by
  alternatives from the full bank catalog. This is presentation order, not
  a best-match badge. The focus bank is configured in `src/recommend/comparison.py`.
- The summary compares the featured card with the first alternative using
  known fees and cash-back category rates. It includes positive and negative
  impacts, ties, caps and activation requirements. It does not convert points
  to cash or infer missing category rates or fees.
- Fonts and icons are served locally. No account or conversation persistence
  is added; messages still go to Flask and AWS Bedrock for assistant replies.

React with Vite fits the existing Python backend without adding a second
application server in production. See the [React integration guide](https://react.dev/learn/add-react-to-an-existing-project)
and [Vite backend integration guide](https://vite.dev/guide/backend-integration).
