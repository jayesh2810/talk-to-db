const QUESTIONS = [
  'Which customers are most likely to churn in the next 90 days?',
  'Show me our top 10 customers by lifetime value',
  'Which recent orders have the highest fraud risk?',
  'What products should we recommend to VIP customers?',
  'How many orders were placed last month?',
  'Which marketing campaigns are driving the most conversions?',
]

export default function ExampleQuestions({ onSelect }) {
  return (
    <div className="flex flex-col items-center gap-6 py-12 px-4">
      <div className="text-center">
        <h2 className="text-lg font-semibold text-gray-200 mb-1">
          Ask a predictive question
        </h2>
        <p className="text-sm text-gray-500">
          Try one of these examples or type your own
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
