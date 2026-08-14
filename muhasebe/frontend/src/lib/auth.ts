interface CheckAuthResponse {
  authenticated: boolean
  user?: string
}

interface LoginResponse {
  success: boolean
  message?: string
}

export async function checkAuth(): Promise<boolean> {
  try {
    const res = await fetch('/api/check-auth', { credentials: 'include' })
    if (!res.ok) return false
    const data: CheckAuthResponse = await res.json()
    return data.authenticated === true
  } catch {
    return false
  }
}

export async function login(
  username: string,
  password: string
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    })
    const data: LoginResponse = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Giriş başarılı.' : 'Giriş başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function logout(): Promise<void> {
  try {
    await fetch('/api/logout', { method: 'POST', credentials: 'include' })
  } catch {
    // Sessizce geç: yerel oturum durumu zaten temizlenecek.
  }
}
