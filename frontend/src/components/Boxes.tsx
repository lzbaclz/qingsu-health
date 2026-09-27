import type { ReactNode } from 'react'

export function ErrorBox({ error, onClose }: { error: string | null | undefined; onClose?: () => void }) {
  if (!error) return null
  return (
    <div className="box box-error" role="alert">
      <strong>操作未完成：</strong>
      <span>{error}</span>
      {onClose && (
        <button type="button" className="box-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
      )}
    </div>
  )
}

export function SuccessBox({ message, onClose }: { message: string | null | undefined; onClose?: () => void }) {
  if (!message) return null
  return (
    <div className="box box-success" role="status">
      <span>{message}</span>
      {onClose && (
        <button type="button" className="box-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
      )}
    </div>
  )
}

export function WarnBox({ children }: { children: ReactNode }) {
  return <div className="box box-warn">{children}</div>
}

export function InfoBox({ children }: { children: ReactNode }) {
  return <div className="box box-info">{children}</div>
}

export function Loading({ text = '加载中…' }: { text?: string }) {
  return <div className="loading">{text}</div>
}

export function Empty({ text = '暂无数据' }: { text?: string }) {
  return <div className="empty">{text}</div>
}
