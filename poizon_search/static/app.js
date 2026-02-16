// 실행 버튼 찾기
const runBtn = document.getElementById("runBtn");

// 버튼 클릭 이벤트 등록
runBtn.addEventListener("click", async () => {

  // 입력창에서 키워드 읽기
  const keyword = document.getElementById("keyword").value;

  // Flask 서버 /run 으로 POST 요청 보내기
  const res = await fetch("/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      keyword: keyword
    })
  });

  // 서버 응답 JSON 받기
  const json = await res.json();

  // 화면 로그 박스에 출력
  document.getElementById("logBox").textContent =
    "서버 응답:\n" + JSON.stringify(json, null, 2);
});
