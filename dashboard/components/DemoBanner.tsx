export default function DemoBanner() {
  return (
    <div className="sticky top-0 z-40 bg-accent/10 border-b border-accent/30 text-accent px-4 py-2 text-center text-sm font-medium">
      DEMO MODE — viewing sample data.{" "}
      <a
        href="/login"
        className="underline underline-offset-2 font-semibold hover:text-accent/80"
      >
        Sign up
      </a>{" "}
      to use LocalMate with your own business.
    </div>
  );
}
