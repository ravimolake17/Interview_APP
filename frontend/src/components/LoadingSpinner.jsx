export default function LoadingSpinner({ message = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="relative w-16 h-16">
        <div className="absolute inset-0 border-4 border-hr-100 rounded-full" />
        <div className="absolute inset-0 border-4 border-hr-600 rounded-full border-t-transparent animate-spin" />
      </div>
      <p className="mt-4 text-gray-500 font-medium">{message}</p>
    </div>
  );
}
