import ChatWidget from './ChatWidget'

// Maintain backward compatibility for any direct usages of Chat
export default function Chat(props) {
  return <ChatWidget isOpen={true} {...props} />
}

export { ChatWidget }
