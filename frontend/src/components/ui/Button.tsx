import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  children,
  className = '',
  ...props
}) => {
  const base = 'inline-flex items-center justify-center font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1';
  const sizes = { sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2 text-sm' };
  const variants = {
    primary: 'bg-[#1e3a6e] text-white hover:bg-[#162d56]',
    secondary: 'bg-white text-[#1e3a6e] border border-gray-200 hover:bg-gray-50',
    ghost: 'text-gray-500 hover:bg-gray-100',
  };

  return (
    <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
};
