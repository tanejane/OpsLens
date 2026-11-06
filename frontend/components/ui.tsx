import type { ReactNode } from "react";

type PageHeadingProps = {
  eyebrow: string;
  title: string;
  description?: string;
  className?: string;
};

export function PageHeading({ eyebrow, title, description, className = "" }: PageHeadingProps) {
  return <header className={`page-heading ${className}`.trim()}>
    <span className="eyebrow">{eyebrow}</span>
    <h1>{title}</h1>
    {description && <p>{description}</p>}
  </header>;
}

type SectionHeadingProps = {
  eyebrow?: string;
  title: string;
  note?: ReactNode;
  className?: string;
};

export function SectionHeading({ eyebrow, title, note, className = "" }: SectionHeadingProps) {
  return <div className={`section-heading ${className}`.trim()}>
    {eyebrow && <span className="eyebrow">{eyebrow}</span>}
    <h2>{title}</h2>
    {note && <p>{note}</p>}
  </div>;
}
