import requests
import json
import re

DEFAULT_OLLAMA_URL = "http://localhost:11434"

class OllamaService:
    def __init__(self, base_url=DEFAULT_OLLAMA_URL):
        self.base_url = base_url.rstrip('/')

    def check_connection(self):
        """Check if local Ollama daemon is running."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if res.status_code == 200:
                return True, res.json().get('models', [])
            return False, []
        except Exception:
            return False, []

    def get_models(self):
        """Fetch list of installed models from Ollama."""
        is_connected, models = self.check_connection()
        if is_connected and models:
            model_names = [m.get('name') for m in models]
            return {
                "online": True,
                "models": model_names,
                "current_url": self.base_url
            }
        else:
            # Fallback list of models available when offline or when Ollama service isn't active yet
            return {
                "online": False,
                "models": ["llama3:latest", "mistral:latest", "gemma:7b", "phi3:mini", "deepseek-coder:latest"],
                "current_url": self.base_url,
                "notice": "Ollama server offline or not found at URL. Operating in Smart Offline Mode."
            }

    def generate_email(self, prompt, model="llama3", tone="Formal", length="Medium", rag_context="", ocr_text="", sender_name="Koushik", receiver_name="Manager / Recipient"):
        """Generate email subject and body using Ollama API or smart offline generator."""
        is_connected, _ = self.check_connection()
        
        length_guidance = {
            "Short": "CRITICAL: Write an EXTREMELY SHORT and concise email (under 60 words, 2-3 sentences max). No fluff.",
            "Medium": "Write a standard medium length email with 2-3 clear paragraphs (approx 120-180 words).",
            "Long": "Write a HIGHLY DETAILED, comprehensive email with 4-5 thorough paragraphs, background explanation, bullet points, and full context (approx 300+ words)."
        }
        len_rule = length_guidance.get(length, length_guidance["Medium"])

        system_prompt = (
            "You are an expert Email Writer AI Assistant. Your task is to write a high quality, clear, "
            f"and effective email. Sender Name: '{sender_name}'. Receiver/Recipient Name: '{receiver_name}'. Tone: {tone}. Length Requirement: {length} ({len_rule}).\n"
            f"Address the recipient directly as '{receiver_name}' and sign off with '{sender_name}'.\n"
            "Format your final output EXACTLY as follows:\n\n"
            "Subject: [Generated Email Subject]\n\n"
            "[Generated Email Body]"
        )

        full_prompt = f"User Request: {prompt}\n"
        if sender_name:
            full_prompt += f"Sender Name: {sender_name}\n"
        if receiver_name:
            full_prompt += f"Receiver Name: {receiver_name}\n"
        if tone:
            full_prompt += f"Desired Tone: {tone}\n"
        if length:
            full_prompt += f"Desired Length: {length} - {len_rule}\n"
        if ocr_text:
            full_prompt += f"\n--- Extracted Document Text (OCR) ---\n{ocr_text}\n"
        if rag_context:
            full_prompt += f"\n--- Relevant Knowledge Base Context (RAG) ---\n{rag_context}\n"

        if is_connected:
            try:
                # Set max_tokens based on length selection
                max_tokens = 150 if length == "Short" else (400 if length == "Medium" else 900)
                payload = {
                    "model": model,
                    "prompt": f"{system_prompt}\n\n{full_prompt}",
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": max_tokens
                    }
                }
                res = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=60)
                if res.status_code == 200:
                    raw_response = res.json().get('response', '')
                    return self._parse_email_response(raw_response)
            except Exception as e:
                print(f"[Ollama API Error]: {e}. Falling back to Smart Generator.")

        # Smart Fallback AI Engine with Sender, Receiver & Length Integration
        return self._smart_fallback_generator(prompt, tone, length, rag_context, ocr_text, sender_name, receiver_name)

    def _parse_email_response(self, text):
        """Extract subject and body from LLM output."""
        subject_match = re.search(r"Subject:\s*(.*?)(?:\n\n|\n|$)", text, re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove Subject line from body
            body = re.sub(r"Subject:\s*.*?(?:\n\n|\n|$)", "", text, count=1, flags=re.IGNORECASE).strip()
        else:
            lines = text.strip().split('\n')
            subject = lines[0].strip() if lines else "Generated Email Subject"
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text.strip()

        # Clean subject quotes if present
        subject = subject.strip('"\'')
        return {
            "subject": subject or "Generated Email Subject",
            "body": body or text
        }

    def _smart_fallback_generator(self, prompt, tone, length, rag_context="", ocr_text="", sender_name="Koushik", receiver_name="Manager"):
        """Generates contextual, realistic email responses when Ollama is offline."""
        prompt_lower = prompt.lower()
        rec_name = receiver_name if receiver_name else "Recipient"
        snd_name = sender_name if sender_name else "Koushik"

        # Determine subject & body based on user query keywords
        if "leave" in prompt_lower or "sick" in prompt_lower or "vacation" in prompt_lower:
            subject = "Request for Leave of Absence"
            body = (
                f"Dear {rec_name},\n\n"
                "I am writing to formally request a leave of absence for 3 days starting from [Start Date] to [End Date]. "
                "The reason for this request is [briefly state reason, e.g., personal matter / medical leave].\n\n"
                "Before leaving, I will ensure all my current urgent tasks are completed, and I have delegated a colleague "
                "to handle any critical inquiries in my absence. I will also be accessible via email for urgent issues.\n\n"
                "Thank you for your understanding and support.\n\n"
                f"Warm regards,\n{snd_name}"
            )
        elif "job" in prompt_lower or "application" in prompt_lower or "developer" in prompt_lower:
            subject = f"Application for Position - {snd_name}"
            body = (
                f"Dear {rec_name},\n\n"
                "I am excited to submit my application for the open role. With strong technical expertise "
                "and hands-on experience in software development and AI engineering, I am confident in my ability "
                "to add immediate value to your organization.\n\n"
                "Throughout my career, I have successfully built scalable systems, optimized workflows, and collaborated "
                "effectively across cross-functional teams. Enclosed is my resume for your review.\n\n"
                "I look forward to the opportunity to discuss how my qualifications align with your team's goals.\n\n"
                f"Best regards,\n{snd_name}"
            )
        elif "follow up" in prompt_lower or "status" in prompt_lower:
            subject = "Following Up: Project Status & Review"
            body = (
                f"Hi {rec_name},\n\n"
                "I hope this message finds you well.\n\n"
                "I am following up on our previous conversation regarding the project review and deliverables. "
                "Could you please share an update on the progress or next steps when you get a chance?\n\n"
                "Please let me know if you need any additional information from my side.\n\n"
                f"Best regards,\n{snd_name}"
            )
        elif "complaint" in prompt_lower or "issue" in prompt_lower:
            subject = "Attention Required: Feedback Regarding Recent Service"
            body = (
                f"Dear {rec_name},\n\n"
                "I am reaching out regarding a recent issue encountered with your service. "
                "Specifically, [describe problem briefly].\n\n"
                "I would greatly appreciate your prompt assistance in resolving this matter or providing a resolution.\n\n"
                "Thank you for your attention to this issue.\n\n"
                f"Sincerely,\n{snd_name}"
            )
        else:
            cleaned_title = prompt.strip().capitalize()
            subject = f"Regarding: {cleaned_title[:50]}"
            body = (
                f"Dear {rec_name},\n\n"
                f"I am writing regarding {prompt}.\n\n"
            )
            if rag_context:
                body += f"Based on knowledge base information:\n{rag_context[:300]}\n\n"
            if ocr_text:
                body += f"Extracted document reference:\n{ocr_text[:300]}\n\n"
                
            body += (
                "Please review this and let me know your thoughts or if any further action is required.\n\n"
                f"Best regards,\n{snd_name}"
            )

        # Apply Length Modifiers (Short vs Medium vs Long)
        if length == "Short":
            # Compact 2-sentence draft
            short_body = f"Dear {rec_name},\n\nI am reaching out regarding {prompt}.\n\nPlease let me know your feedback or if any action is needed.\n\nBest regards,\n{snd_name}"
            body = short_body
        elif length == "Long":
            # Comprehensive 4-paragraph draft with background details & bullet points
            long_body = (
                f"Dear {rec_name},\n\n"
                f"I hope this email finds you well. I am writing to provide a detailed update and formal request regarding {prompt}.\n\n"
                "To give you complete context, here are the key operational points and details:\n"
                f"• Overview: Primary request concerning {prompt}.\n"
                "• Timeline & Scope: Immediate implementation with complete team coordination.\n"
                "• Next Steps: Verification of requirements and follow-up review.\n\n"
                "Please review the attached details and let me know if you would like to schedule a brief call to discuss this further. "
                "I appreciate your time and assistance in moving this forward.\n\n"
                f"Best regards,\n{snd_name}\n[Contact Details | Email Writer AI]"
            )
            body = long_body

        # Adjust tone styling for offline generator
        if tone in ["Casual", "Friendly"]:
            body = body.replace("Dear", "Hi").replace("Sincerely", "Cheers").replace("Warm regards", "Best")
        elif tone == "Urgent":
            subject = "[URGENT] " + subject
            body = "URGENT ACTION REQUIRED:\n\n" + body
        elif tone in ["Empathetic", "Polite", "Empathetic / Polite"]:
            body = "Thank you for reaching out. " + body.replace("I am writing", "I wanted to personally reach out and check in")
        elif tone == "Apologetic":
            subject = "Apologies: " + subject
            body = "We sincerely apologize for any inconvenience caused.\n\n" + body
        elif tone in ["Authoritative", "Executive"]:
            body = "DIRECTIVE:\n\n" + body.replace("I am writing to formally request", "Please ensure the following is completed:")
        elif tone in ["Assertive", "Firm"]:
            body = body + "\n\nPlease note that prompt resolution is required by end of day."
        elif tone == "Enthusiastic":
            subject = subject + " 🎉"
            body = body.replace("I am writing", "I am super excited to share").replace("Best regards", "Excited to connect!")
        elif tone == "Diplomatic":
            body = body.replace("specifically", "upon careful consideration").replace("I would greatly appreciate", "We look forward to finding a mutually beneficial solution regarding")

        return {
            "subject": subject,
            "body": body,
            "note": f"Generated in {tone} tone ({length} length format). Connect local Ollama instance at http://localhost:11434 to switch to live LLM."
        }
