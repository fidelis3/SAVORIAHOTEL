import React from "react";
import { nanoid } from "nanoid";

export default function ChatPopup(props) {
    const [messages, setMessages] = React.useState([]);
    const [inputMessage, setInputMessage] = React.useState("");
    const [isLoading, setIsLoading] = React.useState(false);
    const [isMinimized, setIsMinimized] = React.useState(false);
    const [showSuggestions, setShowSuggestions] = React.useState(true);
    const [typingSpeed, setTypingSpeed] = React.useState(30);
    const [theme, setTheme] = React.useState('default');
    const [lastSeen, setLastSeen] = React.useState(new Date());

    const suggestions = [
        { text: "What's the most popular dish?", icon: "⭐" },
        { text: "Do you have vegetarian options?", icon: "🥗" },
        { text: "Tell me about wine pairings", icon: "🍷" },
        { text: "What's the chef's special today?", icon: "👨‍🍳" },
        { text: "I have dietary restrictions", icon: "🏥" },
        { text: "Show me dessert options", icon: "🍰" }
    ];

    const quickReplies = [
        "Tell me more",
        "That sounds great!",
        "What else?",
        "Perfect, thanks!"
    ];

    React.useEffect(() => {
        const messagesDiv = document.getElementById("messages-container");
        if (messagesDiv) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    }, [messages]);

    // Auto-resize textarea
    React.useEffect(() => {
        const textarea = document.getElementById('message-input');
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        }
    }, [inputMessage]);

    const addMessage = (msg, isUser, isTyping = false) => {
        const newMessage = {
            content: msg,
            isUser,
            isTyping,
            id: nanoid(),
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            reactions: [],
            delivered: true,
            seen: false
        };

        setMessages((prev) => [...prev, newMessage]);
        return newMessage;
    };

    const typeMessage = async (message, targetId) => {
        const words = message.split(' ');
        let currentText = '';
        
        for (let i = 0; i < words.length; i++) {
            currentText += (i > 0 ? ' ' : '') + words[i];
            
            setMessages((prev) =>
                prev.map((msg) =>
                    msg.id === targetId
                        ? { ...msg, content: currentText, isTyping: i < words.length - 1 }
                        : msg
                )
            );
            
            if (i < words.length - 1) {
                await new Promise(resolve => setTimeout(resolve, typingSpeed));
            }
        }
    };

    const sendMessageFromText = async (text) => {
        if (text.trim() === "") return;
        
        setIsLoading(true);
        setShowSuggestions(false);
        const userMessage = addMessage(text, true);
        
        // Mark user message as seen after a delay
        setTimeout(() => {
            setMessages(prev => prev.map(msg => 
                msg.id === userMessage.id ? { ...msg, seen: true } : msg
            ));
        }, 1000);

        const typingMessage = addMessage("", false, true);

        const apiUrl = "https://savoria20-production.up.railway.app/ask_rag";
        const requestBody = {
            question: text,
        };

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}`);
            }

            const data = await response.json();
            const aiAnswer = data.answer;

            // Type the message with animation
            await typeMessage(aiAnswer, typingMessage.id);

        } catch (error) {
            console.error("Error fetching AI response:", error);
            await typeMessage("Sorry, I'm having trouble connecting. Please try again later.", typingMessage.id);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSendMessage = () => {
        if (inputMessage.trim() && !isLoading) {
            sendMessageFromText(inputMessage);
            setInputMessage("");
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const addReaction = (messageId, emoji) => {
        setMessages(prev => prev.map(msg => 
            msg.id === messageId 
                ? { ...msg, reactions: [...(msg.reactions || []), emoji] }
                : msg
        ));
    };

    const TypingIndicator = () => (
        <div className="flex items-center space-x-2 text-gray-500">
            <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gradient-to-r from-amber-400 to-amber-600 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gradient-to-r from-amber-400 to-amber-600 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gradient-to-r from-amber-400 to-amber-600 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
            </div>
            <span className="text-sm ml-2 font-medium">Savoria chef is crafting a response...</span>
        </div>
    );

    const MessageStatus = ({ message }) => (
        <div className="flex items-center space-x-1 mt-1">
            {message.delivered && (
                <div className="flex">
                    <div className="w-3 h-3 text-amber-600">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                        </svg>
                    </div>
                    {message.seen && (
                        <div className="w-3 h-3 text-blue-600 -ml-1">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                            </svg>
                        </div>
                    )}
                </div>
            )}
            <span className="text-xs text-gray-400">{message.timestamp}</span>
        </div>
    );

    if (isMinimized) {
        return (
            <div className="fixed bottom-6 right-6 z-50">
                <button
                    onClick={() => setIsMinimized(false)}
                    className="w-16 h-16 bg-gradient-to-br from-amber-900 via-amber-800 to-amber-900 hover:from-amber-800 hover:via-amber-700 hover:to-amber-800 text-white rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 animate-pulse"
                >
                    <span className="text-2xl">👨‍🍳</span>
                    {messages.length > 0 && (
                        <div className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs font-bold animate-bounce">
                            {messages.filter(m => !m.isUser).length}
                        </div>
                    )}
                </button>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 bg-black bg-opacity-40 z-50 flex justify-center items-center p-4 sm:justify-end sm:items-end sm:pb-6 sm:pr-6 backdrop-blur-lg">
            <div className="bg-white rounded-3xl shadow-2xl w-full h-full max-h-screen overflow-hidden sm:w-[440px] sm:h-[750px] sm:max-h-[95vh] relative animate-in slide-in-from-bottom-8 duration-500 sm:slide-in-from-right-8 border border-gray-200">
                
                {/* Header */}
                <div className="bg-gradient-to-br from-amber-900 via-amber-800 to-amber-900 text-white p-6 rounded-t-3xl relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-10 animate-pulse"></div>
                    <div className="relative z-10">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-4">
                                <div className="relative">
                                    <div className="w-12 h-12 bg-white bg-opacity-20 rounded-2xl flex items-center justify-center backdrop-blur-sm">
                                        <span className="text-2xl">👨‍🍳</span>
                                    </div>
                                    <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white animate-pulse"></div>
                                </div>
                                <div>
                                    <h2 className="text-xl font-bold">Savoria AI Chef</h2>
                                    <p className="text-sm text-amber-100 flex items-center space-x-1">
                                        <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                                        <span>Always here to help</span>
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center space-x-2">
                                <button
                                    onClick={() => setIsMinimized(true)}
                                    className="w-10 h-10 rounded-2xl bg-white bg-opacity-20 hover:bg-opacity-30 transition-all duration-300 flex items-center justify-center backdrop-blur-sm"
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                                    </svg>
                                </button>
                                <button
                                    onClick={props.onClose}
                                    className="w-10 h-10 rounded-2xl bg-white bg-opacity-20 hover:bg-opacity-30 transition-all duration-300 flex items-center justify-center backdrop-blur-sm"
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Messages Container */}
                <div
                    id="messages-container"
                    className="flex-1 overflow-y-auto p-6 space-y-6 bg-gradient-to-br from-gray-50 to-white"
                    style={{ height: 'calc(100% - 260px)' }}
                >
                    {messages.length === 0 && (
                        <>
                            <div className="text-center py-12">
                                <div className="text-8xl mb-6 animate-bounce">🍽️</div>
                                <h3 className="text-2xl font-bold text-gray-800 mb-3">Welcome to Savoria!</h3>
                                <p className="text-gray-600 text-lg leading-relaxed max-w-sm mx-auto">
                                    Your personal AI chef is ready to help you discover amazing dishes, ingredients, and create unforgettable dining experiences.
                                </p>
                                <div className="mt-8 p-4 bg-amber-50 rounded-2xl border border-amber-200">
                                    <p className="text-sm text-amber-800 font-medium">✨ Pro tip: I can help with dietary restrictions, wine pairings, and personalized recommendations!</p>
                                </div>
                            </div>
                            
                            {/* Suggestions inside messages container */}
                            <div className="pb-4">
                                <p className="text-sm text-gray-600 mb-4 font-medium">🚀 Quick starters:</p>
                                <div className="grid grid-cols-2 gap-3">
                                    {suggestions.map((suggestion, index) => (
                                        <button
                                            key={index}
                                            onClick={() => sendMessageFromText(suggestion.text)}
                                            disabled={isLoading}
                                            className="bg-gradient-to-r from-gray-50 to-gray-100 hover:from-amber-50 hover:to-amber-100 disabled:opacity-50 disabled:cursor-not-allowed py-3 px-4 rounded-2xl text-sm text-gray-700 transition-all duration-300 border border-gray-200 hover:border-amber-300 transform hover:scale-105 hover:shadow-md"
                                        >
                                            <div className="flex items-center space-x-2">
                                                <span className="text-lg">{suggestion.icon}</span>
                                                <span className="font-medium">{suggestion.text}</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                    
                    {messages.map((message, index) => (
                        <div
                            key={message.id}
                            className={`flex ${message.isUser ? 'justify-end' : 'justify-start'} animate-in fade-in-0 slide-in-from-bottom-4 duration-500`}
                            style={{ animationDelay: `${index * 100}ms` }}
                        >
                            <div className={`max-w-[85%] ${message.isUser ? 'order-2' : 'order-1'}`}>
                                <div
                                    className={`px-6 py-4 rounded-3xl relative ${
                                        message.isUser
                                            ? "bg-gradient-to-br from-amber-900 via-amber-800 to-amber-900 text-white rounded-br-lg shadow-lg"
                                            : "bg-white text-gray-800 rounded-bl-lg shadow-lg border border-gray-100"
                                    }`}
                                >
                                    {message.isTyping ? (
                                        <TypingIndicator />
                                    ) : (
                                        <>
                                            <div className="text-sm leading-relaxed font-medium">{message.content}</div>
                                            {message.reactions && message.reactions.length > 0 && (
                                                <div className="flex space-x-1 mt-2">
                                                    {message.reactions.map((reaction, i) => (
                                                        <span key={i} className="text-lg">{reaction}</span>
                                                    ))}
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                                {!message.isTyping && (
                                    <div className={`flex items-center mt-2 ${message.isUser ? 'justify-end' : 'justify-start'}`}>
                                        {message.isUser ? (
                                            <MessageStatus message={message} />
                                        ) : (
                                            <div className="flex items-center space-x-2">
                                                <span className="text-xs text-gray-400">{message.timestamp}</span>
                                                <div className="flex space-x-1">
                                                    {['👍', '❤️', '😊', '🔥'].map((emoji) => (
                                                        <button
                                                            key={emoji}
                                                            onClick={() => addReaction(message.id, emoji)}
                                                            className="w-6 h-6 text-sm hover:scale-125 transition-transform duration-200 opacity-60 hover:opacity-100"
                                                        >
                                                            {emoji}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Quick Replies */}
                {messages.length > 0 && messages[messages.length - 1] && !messages[messages.length - 1].isUser && !isLoading && (
                    <div className="px-6 py-2 bg-white border-t border-gray-100">
                        <p className="text-xs text-gray-500 mb-2">💬 Quick replies:</p>
                        <div className="flex flex-wrap gap-2">
                            {quickReplies.map((reply, index) => (
                                <button
                                    key={index}
                                    onClick={() => sendMessageFromText(reply)}
                                    className="bg-gradient-to-r from-amber-100 to-amber-200 hover:from-amber-200 hover:to-amber-300 py-2 px-4 rounded-full text-sm text-amber-800 font-medium transition-all duration-300 transform hover:scale-105 border border-amber-300"
                                >
                                    {reply}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Suggestions */}
                {showSuggestions && messages.length === 0 && (
                    <div className="px-6 py-4 bg-white border-t border-gray-100">
                        <p className="text-sm text-gray-600 mb-4 font-medium">🚀 Quick starters:</p>
                        <div className="grid grid-cols-2 gap-3">
                            {suggestions.map((suggestion, index) => (
                                <button
                                    key={index}
                                    onClick={() => sendMessageFromText(suggestion.text)}
                                    disabled={isLoading}
                                    className="bg-gradient-to-r from-gray-50 to-gray-100 hover:from-amber-50 hover:to-amber-100 disabled:opacity-50 disabled:cursor-not-allowed py-3 px-4 rounded-2xl text-sm text-gray-700 transition-all duration-300 border border-gray-200 hover:border-amber-300 transform hover:scale-105 hover:shadow-md"
                                >
                                    <div className="flex items-center space-x-2">
                                        <span className="text-lg">{suggestion.icon}</span>
                                        <span className="font-medium">{suggestion.text}</span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Suggestions - Always visible above input */}
                {messages.length === 0 && (
                    <div className="px-6 py-4 bg-white border-t border-gray-100">
                        <p className="text-sm text-gray-600 mb-4 font-medium">🚀 Quick starters:</p>
                        <div className="grid grid-cols-2 gap-3">
                            {suggestions.map((suggestion, index) => (
                                <button
                                    key={index}
                                    onClick={() => sendMessageFromText(suggestion.text)}
                                    disabled={isLoading}
                                    className="bg-gradient-to-r from-gray-50 to-gray-100 hover:from-amber-50 hover:to-amber-100 disabled:opacity-50 disabled:cursor-not-allowed py-3 px-4 rounded-2xl text-sm text-gray-700 transition-all duration-300 border border-gray-200 hover:border-amber-300 transform hover:scale-105 hover:shadow-md"
                                >
                                    <div className="flex items-center space-x-2">
                                        <span className="text-lg">{suggestion.icon}</span>
                                        <span className="font-medium">{suggestion.text}</span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Input Area - Fixed at bottom */}
                <div className="sticky bottom-0 p-6 bg-white border-t border-gray-100 rounded-b-3xl shadow-lg">
                    <div className="flex items-end space-x-4">
                        <div className="flex-1 relative">
                            <textarea
                                id="message-input"
                                value={inputMessage}
                                onChange={(e) => setInputMessage(e.target.value)}
                                onKeyPress={handleKeyPress}
                                disabled={isLoading}
                                className="w-full p-4 pr-16 border-2 border-gray-200 rounded-3xl resize-none focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium placeholder-gray-400 transition-all duration-300 bg-gradient-to-r from-gray-50 to-white"
                                placeholder="Type your culinary question..."
                                rows="1"
                                style={{ minHeight: '56px', maxHeight: '120px' }}
                            />
                            <button
                                onClick={handleSendMessage}
                                disabled={!inputMessage.trim() || isLoading}
                                className="absolute right-3 top-1/2 transform -translate-y-1/2 w-10 h-10 bg-gradient-to-r from-amber-900 to-amber-800 hover:from-amber-800 hover:to-amber-700 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed text-white rounded-2xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 shadow-lg"
                            >
                                {isLoading ? (
                                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                ) : (
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                    <div className="flex items-center justify-between mt-3 text-xs text-gray-500">
                        <span>Press Enter to send, Shift+Enter for new line</span>
                        <span className="flex items-center space-x-1">
                            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                            <span>Secure & Private</span>
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}