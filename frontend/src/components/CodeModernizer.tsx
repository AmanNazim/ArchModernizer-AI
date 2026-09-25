"use client";

/**
 * CodeModernizer – Tab 1
 *
 * Lets the user paste legacy code OR upload a file, sends it to
 * POST /api/refactor, and renders a side-by-side diff view of the
 * original vs the generated microservice blueprints.
 */

import { useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────

interface ModuleBlueprint {
  name: string;
  description: string;
  suggested_language: string;
  code_snippet: string;
}

interface RefactorResponse {
  original_lines: number;
  modules: ModuleBlueprint[];
  summary: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const PLACEHOLDER_CODE = `# Example: monolithic Flask app
from flask import Flask, request, jsonify
import sqlite3, smtplib, hashlib

app = Flask(__name__)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    conn = sqlite3.connect('users.db')
    pw_hash = hashlib.sha256(data['password'].encode()).hexdigest()
    conn.execute("INSERT INTO users VALUES (?,?)", (data['email'], pw_hash))
    conn.commit()
    smtplib.SMTP('smtp.example.com').sendmail('no-reply@example.com', data['email'], 'Welcome!')
    return jsonify({'status': 'ok'})

@app.route('/data', methods=['GET'])
def get_data():
    conn = sqlite3.connect('data.db')
    rows = conn.execute("SELECT * FROM records").fetchall()
    return jsonify(rows)

if __name__ == '__main__':
    app.run(debug=True)
`;

// ── Component ──────────────────────────────────────────────────────────────

export default function CodeModernizer() {
  const [code, setCode] = useState(PLACEHOLDER_CODE);
  const [result, setResult] = useState<RefactorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeModule, setActiveModule] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleRefactor() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const fd = new FormData();
      const fileInput = fileRef.current;
      if (fileInput?.files?.[0]) {
        fd.append("file", fileInput.files[0]);
      } else {
        fd.append("code", code);
      }

      const res = await fetch(`${API_BASE}/api/refactor`, {
        method: "POST",
        body: fd,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Refactor request failed");
      }

      const data: RefactorResponse = await res.json();
      setResult(data);
      setActiveModule(0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Section header ── */}
      <div>
        <h2 className="text-lg font-semibold">Code Modernizer</h2>
        <p className="text-sm text-gray-400 mt-1">
          Paste your legacy code or upload a source file. The AI will decompose
          it into independent microservice blueprints.
        </p>
      </div>

      {/* ── Input + diff layout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Input */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Legacy Code
            </span>
            <label className="cursor-pointer text-xs text-blue-400 hover:underline">
              Upload file
              <input
                ref={fileRef}
                type="file"
                accept=".py,.js,.ts,.java,.go,.rb,.php,.cs,.cpp,.c"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) setCode(`[File selected: ${e.target.files[0].name}]`);
                }}
              />
            </label>
          </div>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            rows={20}
            spellCheck={false}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg p-4 text-sm font-mono text-gray-200 resize-none focus:outline-none focus:border-blue-600"
          />
          <button
            onClick={handleRefactor}
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-sm font-medium transition-colors"
          >
            {loading ? "Analysing…" : "⚙️ Refactor to Microservices"}
          </button>
          {error && (
            <p className="text-red-400 text-sm bg-red-950 border border-red-800 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        {/* Right: Output */}
        <div className="flex flex-col gap-3">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Microservice Blueprints
          </span>

          {result ? (
            <>
              {/* Summary banner */}
              <div className="bg-blue-950 border border-blue-800 rounded-lg px-4 py-3 text-sm text-blue-200">
                {result.summary}
              </div>

              {/* Module tabs */}
              <div className="flex gap-2 flex-wrap">
                {result.modules.map((mod, idx) => (
                  <button
                    key={mod.name}
                    onClick={() => setActiveModule(idx)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      activeModule === idx
                        ? "bg-blue-600 text-white"
                        : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                    }`}
                  >
                    {mod.name}
                  </button>
                ))}
              </div>

              {/* Module detail */}
              {result.modules[activeModule] && (
                <div className="flex flex-col gap-2">
                  <div className="bg-gray-800 rounded-lg px-4 py-3 text-sm">
                    <p className="text-gray-400 mb-1">
                      {result.modules[activeModule].description}
                    </p>
                    <span className="text-xs text-green-400">
                      🛠 {result.modules[activeModule].suggested_language}
                    </span>
                  </div>
                  <pre className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-xs text-green-300 font-mono overflow-auto max-h-80 whitespace-pre-wrap">
                    {result.modules[activeModule].code_snippet}
                  </pre>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 bg-gray-900 border border-dashed border-gray-700 rounded-lg flex items-center justify-center text-gray-600 text-sm min-h-[400px]">
              Refactored blueprints will appear here
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
