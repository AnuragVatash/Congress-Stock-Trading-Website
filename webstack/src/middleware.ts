import { NextResponse } from 'next/server';

export function middleware() {
  const res = NextResponse.next();

  // Only enforce security headers in production to avoid breaking Next.js dev HMR/Turbopack
  const isProd = process.env.NODE_ENV === 'production';
  if (!isProd) {
    return res;
  }

  // Strong CSP in enforcement mode (prod only). Keep permissive enough for Next/analytics but avoid eval.
  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://vitals.vercel-insights.com https://va.vercel-scripts.com",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' https://unitedstates.github.io data:",
    "connect-src 'self' https://vitals.vercel-insights.com",
    "font-src 'self' data:",
    "frame-ancestors 'self'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ');

  res.headers.set('Content-Security-Policy', csp);
  res.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
  res.headers.set('X-Frame-Options', 'SAMEORIGIN');
  res.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.headers.set('X-Content-Type-Options', 'nosniff');
  res.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');

  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};


