const KEY = 'lumora_workspace_account_id'

export function getWorkspaceAccountId(): string | null {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function setWorkspaceAccountId(accountId: string) {
  try {
    sessionStorage.setItem(KEY, accountId)
  } catch {
    /* ignore */
  }
}
