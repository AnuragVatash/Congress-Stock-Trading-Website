import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

export function middleware(req: NextRequest) {
  const res = NextResponse.next();

  // Only enforce security headers in production to avoid breaking Next.js dev HMR/Turbopack
  const isProd = process.env.NODE_ENV === 'production';
  if (!isProd) {
    return res;
  }

  // Strong CSP in enforcement mode (prod only)
  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' https://unitedstates.github.io data:",
    "connect-src 'self'",
    "font-src 'self' data:",
    "frame-ancestors 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "require-trusted-types-for 'script'",
  ].join('; ');

  res.headers.set('Content-Security-Policy', csp);
  res.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
  res.headers.set('X-Frame-Options', 'SAMEORIGIN');

  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};


