import { useState } from 'react';
import './UI.css'; // We will add the styles to this file

function BlurrableText({ text, prefix = "" }) {
  const [isBlurred, setIsBlurred] = useState(true);

  if (!text) {
    return null;
  }

  // When clicked, reveal the text. If already revealed, do nothing.
  const handleClick = () => {
    if (isBlurred) {
      setIsBlurred(false);
    }
  };

  return (
    <span
      className={`blurrable-container ${isBlurred ? 'blurred' : ''}`}
      onClick={handleClick}
      title={isBlurred ? 'Click to reveal' : ''}
    >
      {prefix}
      <span className="blurrable-content">{text}</span>
    </span>
  );
}

export default BlurrableText;