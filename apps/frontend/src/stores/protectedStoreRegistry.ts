export type ProtectedStoreCleanup = () => void;

const cleanups = new Set<ProtectedStoreCleanup>();

export function registerProtectedStoreCleanup(cleanup: ProtectedStoreCleanup): () => void {
  cleanups.add(cleanup);
  return () => cleanups.delete(cleanup);
}

export function clearProtectedStores(): Error[] {
  const errors: Error[] = [];
  for (const cleanup of cleanups) {
    try {
      cleanup();
    } catch (error: unknown) {
      errors.push(error instanceof Error ? error : new Error("受保护状态清理失败"));
    }
  }
  return errors;
}

export function resetProtectedStoreRegistryForTests(): void {
  cleanups.clear();
}
