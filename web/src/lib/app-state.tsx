"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, type AppState } from "./api";

interface AppStateValue {
  state: AppState | null;
  error: string | null;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AppStateValue>({ state: null, error: null, refresh: async () => {} });

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AppState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setState(await api<AppState>("/api/state"));
      setError(null);
    } catch {
      setError("Can't reach the Fineprint API. Start it with: uvicorn api.main:app --port 8000");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return <Ctx.Provider value={{ state, error, refresh }}>{children}</Ctx.Provider>;
}

export const useAppState = () => useContext(Ctx);
