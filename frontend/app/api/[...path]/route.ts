import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const upstreamBase = (process.env.OPSLENS_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const upstreamUrl = `${upstreamBase}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  let upstream: Response;

  try {
    upstream = await fetch(upstreamUrl, {
      method: request.method,
      // Preserve browser CSRF context verbatim; never replace Origin with the upstream host.
      headers: Object.fromEntries(["content-type", "cookie", "origin", "sec-fetch-site"].flatMap((key) => request.headers.has(key) ? [[key, request.headers.get(key)!]] : [])),
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(path[0] === "investigations" ? 120_000 : 30_000),
    });
  } catch (error) {
    console.error("OpsLens API upstream request failed", { path: request.nextUrl.pathname, upstreamUrl, error });
    return NextResponse.json({ detail: { status: "API_UNAVAILABLE", reason: "The local FastAPI service could not be reached. Start it on the configured API URL and check its logs.", upstream: upstreamBase } }, { status: 503 });
  }

  const contentType = upstream.headers.get("content-type") || "unspecified";
  const raw = await upstream.text();
  try {
    const payload = JSON.parse(raw);
    if (!contentType.toLowerCase().includes("json")) {
      return NextResponse.json({ detail: { status: "INVALID_UPSTREAM_RESPONSE", reason: "FastAPI returned a non-JSON response.", upstream_status: upstream.status, upstream_content_type: contentType, upstream_excerpt: raw.slice(0, 240) } }, { status: 502 });
    }
    const response = NextResponse.json(payload, { status: upstream.status });
    const cookie = upstream.headers.get("set-cookie");
    if (cookie) response.headers.set("set-cookie", cookie);
    response.headers.set("cache-control", "no-store");
    return response;
  } catch {
    console.error("OpsLens API returned a non-JSON body", { path: request.nextUrl.pathname, upstreamStatus: upstream.status, contentType, excerpt: raw.slice(0, 240) });
    return NextResponse.json({ detail: { status: "INVALID_UPSTREAM_RESPONSE", reason: "FastAPI returned a non-JSON response.", upstream_status: upstream.status, upstream_content_type: contentType, upstream_excerpt: raw.slice(0, 240) } }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
