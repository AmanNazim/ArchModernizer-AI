==================================================
SPECIFICATION 08: REPOVIBE CHAT INTERFACE (FRONTEND)
==================================================

1. MODULE OBJECTIVE:
   Build the interactive RepoVibe chatbot UI component for the Next.js frontend. This interface serves as the primary conversational surface for the repository RAG engine, allowing developers to query architectural insights, locate legacy logic, and understand code relationships.

2. CHAT INTERFACE ARCHITECTURE:

- **Message Container:**
  - Create an auto-scrolling message list window that displays the conversation history between the user and the repository assistant.
  - Message bubbles should clearly differentiate between User messages (right-aligned, distinct background color) and Assistant responses (left-aligned with an avatar icon).
- **Input Bar:**
  - Implement a pinned bottom input field with a send button and submit-on-Enter keyboard handler (Shift+Enter for newlines).
  - Disable input controls and display a pulsating "Analyzing codebase..." typing indicator while an API request is pending.
- **Empty State:**
  - If no chat history exists, render quick-prompt suggestion chips (e.g., _"Explain the main architecture"_, _"Where are the API routes defined?"_, _"List core dependencies"_).

3. API INTEGRATION (`/api/onboarding/chat`):

- Connect the message submission handler to perform a POST request to `http://127.0.0.1:8000/api/onboarding/chat`.
- **Payload Schema:** `{ "job_id": string, "query": string }`
- **Response Handling:**
  - On success, append the returned `{ answer, sources }` payload to the conversation state.
  - Extracted `sources` array items (containing `file_path` and `lines`) should be rendered as clickable metadata tags beneath the AI response bubble.

4. MARKDOWN & CODE RENDERING:

- Integrate `react-markdown` (along with `remark-gfm`) inside the assistant message bubbles to support rich text formatting:
  - Render inline code blocks and multi-line code blocks using `react-syntax-highlighter`.
  - Render bullet points, bold key terms, and markdown tables cleanly.
- Include a "Copy Code" utility button on all generated code blocks within chat responses.

5. EXECUTION & STYLING CONSTRAINTS:

- Declare the component with the `"use client"` directive to enable React state hooks (`useState`, `useEffect`, `useRef`).
- Use an explicit `useRef` attachment to automatically scroll to the bottom of the message container whenever new content or streaming tokens are added.
- **Guardrails:** If no `job_id` exists in the global Zustand state or if the repository index is not ready, display a banner prompting the user to complete repository ingestion first.
