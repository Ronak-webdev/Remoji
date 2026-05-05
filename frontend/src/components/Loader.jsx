import React from 'react';
import styled from 'styled-components';

const Loader = () => {
  return (
    <StyledWrapper>
      <div className="loader" />
    </StyledWrapper>
  );
}

const StyledWrapper = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  
  .loader {
    width: 128px; /* Doubled size as requested */
    height: 128px;
    position: relative;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .loader:before {
    content: "";
    position: absolute;
    left: 0;
    bottom: 0;
    width: 80px; /* Scaled */
    height: 80px;
    transform: rotate(45deg) translate(30%, 40%);
    background: #2e86de;
    box-shadow: 64px -68px 0 10px #0097e6;
    animation: slide 2s infinite ease-in-out alternate;
  }

  .loader:after {
    content: "";
    position: absolute;
    left: 20px;
    top: 20px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #0097e6;
    transform: rotate(0deg);
    transform-origin: 70px 290px;
    animation: rotate 2s infinite ease-in-out;
  }

  @keyframes slide {
    0% , 100% {
      bottom: -70px
    }

    25% , 75% {
      bottom: -4px
    }

    20% , 80% {
      bottom: 4px
    }
  }

  @keyframes rotate {
    0% {
      transform: rotate(-15deg)
    }

    25% , 75% {
      transform: rotate(0deg)
    }

    100% {
      transform: rotate(25deg)
    }
  }`;

export default Loader;
