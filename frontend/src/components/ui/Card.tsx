import React from "react";

export interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <div className={`bg-[#20212B] rounded-xl border border-white/[0.08] shadow-xl p-6 text-[#F5F5F5] ${className}`}>
      {children}
    </div>
  );
}
