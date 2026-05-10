const QUESTIONS = [
  'Predict churn for users 1 through 5 in the next 90 days',
  'How much will user 42 spend in the next 30 days?',
  'Recommend top 10 items for user 123',
  'Show me the most expensive items in the catalog',
  'Predict 30-day demand for item 1',
  'List all orders over $100',
]

export default function ExampleQuestions({ onSelect }) {
  return (
    <div className="flex flex-col items-center gap-6 py-12 px-4">
      <div className="text-center">
        <h2 className="text-lg font-semibold text-gray-200 mb-1">
          Ask a predictive question
        </h2>
        <p className="text-sm text-gray-500">
          Powered by KumoRFM — try one of these or type your own
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-2 max-w-3xl">
        {QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="
              px-3 py-2 rounded-lg border border-gray-700 bg-gray-900
              text-sm text-gray-300 text-left
              hover:border-indigo-500 hover:bg-gray-800 hover:text-white
              transition-colors duration-150 cursor-pointer
              max-w-xs
            "
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
