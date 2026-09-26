# Next.js UI Patterns — Reference

Concrete code for each rule in SKILL.md. Match new components to these shapes.

## 1. Reusable skeleton component

```tsx
// components/ui/Skeleton.tsx
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-gray-200 dark:bg-gray-700 ${className}`}
    />
  );
}

// A skeleton that mirrors the shape of the real content — not a generic spinner
export function CardSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4">
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}
```

## 2. Data-fetching component using the skeleton correctly

```tsx
"use client";
import { useEffect, useState } from "react";
import { CardSkeleton } from "@/components/ui/Skeleton";

interface Product {
  id: string;
  name: string;
  price: number;
  imageUrl: string;
}

export function ProductCard({ productId }: { productId: string }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/products/${productId}`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setProduct(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this product.");
      });
    return () => {
      cancelled = true;
    };
  }, [productId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!product) return <CardSkeleton />;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4 sm:flex-row sm:items-center">
      <img
        src={product.imageUrl}
        alt={product.name}
        className="h-40 w-full rounded-md object-cover sm:h-20 sm:w-20"
      />
      <div>
        <h3 className="font-medium text-gray-900">{product.name}</h3>
        <p className="text-sm text-gray-500">${product.price.toFixed(2)}</p>
      </div>
    </div>
  );
}
```

Note the three states handled explicitly — loading (skeleton), error, and loaded — rather than only the happy path.

## 3. Custom modal built without a UI library

```tsx
"use client";
import { useEffect } from "react";

export function Modal({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800"
      >
        {children}
      </div>
    </div>
  );
}
```

Semantic `role="dialog"`/`aria-modal`, escape-key handling, and a backdrop — built with plain elements and Tailwind, no MUI/Radix component pulled in for something this size.

## 4. Responsive card grid

```tsx
export function CardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {children}
    </div>
  );
}
```

One column on mobile, scaling up through breakpoints — never a fixed multi-column grid that overflows on a narrow viewport.
