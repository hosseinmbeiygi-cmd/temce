interface CardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
  headerClassName?: string;
}

export function Card({ title, subtitle, children, className = "", actions, headerClassName = "" }: CardProps) {
  return (
    <div className={`card ${className}`}>
      {(title || actions) && (
        <div className={`card-header ${headerClassName}`}>
          <div>
            {title && <div className="card-title">{title}</div>}
            {subtitle && <div className="card-subtitle">{subtitle}</div>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className="card-content">{children}</div>
    </div>
  );
}

export function CardAction({ children, active, onClick }: { children: React.ReactNode; active?: boolean; onClick?: () => void }) {
  return (
    <div className={`card-action ${active ? "active" : ""}`} onClick={onClick}>
      {children}
    </div>
  );
}
