# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | ĐẠT (0.757 ≥ 0.6, 0.857 ≥ 0.8, 0.8 ≥ 0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | KHÔNG ĐẠT (κ=0.375 < 0.6, R=0.3 < 0.7) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | Reply xưng hô "Em... anh... nha", vi phạm chuẩn văn phong CSKH chuyên nghiệp của LogiX. |
| 2 | H-017 | PASS | FAIL | Người đúng | Reply dùng từ "bạn ơi... nha" thiếu chuẩn mực trang trọng trong giải quyết khiếu nại. |
| 3 | H-029 | PASS | FAIL | Người đúng | Câu "không cần nhắn thêm" có giọng điệu gắt gỏng, thiếu nhã nhặn với khách hàng. |
| 4 | H-042 | FAIL | PASS | Người đúng | Reply giải thích rõ số tiền và thời gian tiền về (3-5 ngày), chuẩn lịch sự nhưng judge bắt lỗi quá khắt khe (FP). |
| 5 | HL-016 | PASS | FAIL | Người đúng | Judge helpful bỏ sót (FN=21): khách khiếu nại nhưng chỉ xin lỗi chung chung, không giải quyết đúng trọng tâm vấn đề. |

## Kết luận
- **Tiêu chí bị loại**: `helpful` bị loại vì Recall quá thấp (R=0.300) và Cohen's Kappa chỉ đạt 0.375 (dưới ngưỡng 0.6). Ma trận nhầm lẫn: `tp=9, fp=0, fn=21, tn=70`. Judge bỏ sót tới 21 trường hợp phản hồi không có ích (FN=21 / 30 ca lỗi), dẫn đến tỷ lệ lỗi quan sát chỉ 9% trong khi tỷ lệ lỗi thực tế là 30%. Không được dùng judge này làm release gate vì sẽ để lọt phần lớn câu trả lời kém chất lượng.
- **Tiêu chí được chọn**: `tone_ok` đạt chuẩn FLOORS (κ=0.757, P=0.857, R=0.800), có thể sử dụng hỗ trợ đánh giá văn phong.
- **Rủi ro còn lại**: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
