import { useState ,useEffect} from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [input, setInput] = useState('')
  const [videoSrc, setVideoSrc] = useState('')
  const [loading,setLoading] = useState(false)
  // const handleDownload = async () => {
  //   console.log(`clicked`)
  //   try {
  //     const response = await axios.post('http://localhost:2000/post', { info: input }, { responseType: 'blob' })
  //     if (response.status === 200) {
  //       const url = window.URL.createObjectURL(new Blob([response.data], { type: response.data.type }))
  //       setVideoSrc(url)
  //       setLoading(false)
  //     }else{
  //       setLoading(false)
  //     }
  //   } catch (error) {
  //     console.error("There was an error!", error)
  //     setLoading(false)
  //   }
  // }
  const handleDownload = async () => {
    setLoading(true)
    try {
      const response = await axios.post('http://localhost:2000/post', { info: input }, { responseType: 'blob' })
      if (response.status === 200) {
        const url = window.URL.createObjectURL(new Blob([response.data], { type: response.data.type }))
        setVideoSrc(url)
      }
    } catch (error) {
      console.error("There was an error!", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (videoSrc) {
      console.log('Video source updated:', videoSrc)
    }
  }, [videoSrc])
  console.log(videoSrc)

  return (
    <>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder='Enter video URL'
      />

      {loading ? <div><h2>Loading...</h2></div> : <button onClick={handleDownload}>Get Video</button>}

      {videoSrc && (
        <video controls>
          <source src={videoSrc} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      )}
    </>
  )

}

export default App