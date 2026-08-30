import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

async function handleProxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const resolvedParams = await params;
  const pathStr = resolvedParams.path ? resolvedParams.path.join("/") : "";
  const searchParams = req.nextUrl.search;
  const targetUrl = `http://127.0.0.1:8000/api/v1/${pathStr}${searchParams}`;

  const headers = new Headers(req.headers);
  headers.set("host", "127.0.0.1:8000");
  headers.delete("accept-encoding");

  const hasBody = req.method !== "GET" && req.method !== "HEAD";

  try {
    const fetchOptions: RequestInit & { duplex?: string } = {
      method: req.method,
      headers,
    };

    if (hasBody && req.body) {
      fetchOptions.body = req.body;
      fetchOptions.duplex = "half";
    }

    const backendResponse = await fetch(targetUrl, fetchOptions);
    const buffer = await backendResponse.arrayBuffer();

    const responseHeaders = new Headers(backendResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");

    return new NextResponse(buffer, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (err: any) {
    console.error("API proxy error:", err);
    return NextResponse.json(
      { detail: `Failed to proxy request to backend: ${err.message}` },
      { status: 502 }
    );
  }
}

export const GET = handleProxy;
export const POST = handleProxy;
export const PUT = handleProxy;
export const PATCH = handleProxy;
export const DELETE = handleProxy;
export const OPTIONS = handleProxy;
