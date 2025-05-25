import React from "react";

interface Message {
  type: "user" | "ai";
  content: string;
}

interface ChatBubblesProps {
  messages: Message[];
}

export const ChatBubbles: React.FC<ChatBubblesProps> = ({ messages }) => {
  return (
    <div className="pt-[138px] px-[117px] mb-[120px] md:px-8 sm:px-4 sm:pt-[160px]">
      <div className="flex items-start gap-6 mb-[78px] sm:flex-col sm:gap-3 sm:mb-10">
        <div className="w-10 h-10 sm:self-start">
          <div className="w-10 h-10 rounded-full bg-[#B0ACE9] text-white text-2xl font-medium tracking-[-0.24px] flex items-center justify-center">
            S
          </div>
        </div>
        <div className="text-[#1B1F2A] text-[15px] font-medium mt-5">
          explain like im 5
        </div>
      </div>

      <div className="flex items-start gap-6 sm:flex-col sm:gap-3">
        <img
          src="https://cdn.builder.io/api/v1/image/assets/TEMP/9b97c659dbb067c7bcc68c1ce650d78c3876c750?placeholderIfAbsent=true"
          alt=""
          className="w-10 h-10 sm:self-start"
        />
        <div className="text-[#1B1F2A] text-[15px] font-medium leading-7 tracking-[0.15px] max-w-[1144px] -mt-[5px] md:max-w-full sm:text-sm sm:leading-6">
          Our own Large Language Model (LLM) is a type of Al that can learn from
          data. We have trained it on 7 billion parameters which makes it better
          than other LLMs. We are featured on aiplanet.com and work with leading
          enterprises to help them use Al securely and privately. We have a
          Generative Al Stack which helps reduce the hallucinations in LLMs and
          allows enterprises to use Al in their applications.
        </div>
      </div>
    </div>
  );
};
