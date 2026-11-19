export async function GET() {
  try {
    const response = await fetch(`${process.env.API_BASE_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    const body = await response.json();
    return Response.json(body, { status: response.status });
  } catch {
    return Response.json({ status: "unavailable" }, { status: 503 });
  }
}
