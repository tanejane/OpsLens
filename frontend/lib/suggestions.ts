export type SuggestedPromptMode = "Business" | "Analyst";
export type SuggestedQuestion = { title: string; question: string };

export const questionSuggestions: Record<SuggestedPromptMode, SuggestedQuestion[]> = {
  Business: [
    { title: "Revenue and contribution profit", question: "Revenue grew but contribution profit fell from February 2018 to March 2018. Investigate the accounting pressures and state what needs independent validation." },
    { title: "Delivery performance", question: "What was the late delivery rate in June 2018?" },
    { title: "Customer satisfaction", question: "What was the average review score in June 2018?" },
    { title: "Health and beauty category sales", question: "How much health and beauty category item GMV in June 2018?" },
  ],
  Analyst: [
    { title: "Three-domain comparison", question: "Compare finance, late delivery and review scores from February 2018 to March 2018" },
    { title: "Finance accounting pressures", question: "Revenue grew but contribution profit fell from February 2018 to March 2018. Investigate the accounting pressures and state what needs independent validation." },
    { title: "Delivery measurement", question: "What was the late delivery rate in June 2018?" },
    { title: "Review coverage", question: "What was review coverage in June 2018?" },
  ],
};

/** Selecting a prompt only fills the composer. Execution remains a separate user action. */
export function selectSuggestedQuestion(question: string, setQuestion: (value: string) => void): void {
  setQuestion(question);
}
