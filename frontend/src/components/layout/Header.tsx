"use client";

interface HeaderProps {
  title?: string;
}

export default function Header({ title }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b px-6 py-3">
      <h2 className="text-sm font-medium text-[hsl(var(--muted-foreground))]">
        {title || "PersonalAIAssist"}
      </h2>
    </header>
  );
}
