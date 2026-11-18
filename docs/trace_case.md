# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
| --- | --- |
| Trial | `seeded_regression C-002@11` |
| Triệu chứng | Grader Lab 8 báo `FAIL (status resolved != denied)`. Ledger ghi nhận `refund_vnd=20000`, `refund_count=1` trong khi nhãn chuẩn kỳ vọng là từ chối (`status=denied`, `refund_vnd=0`). |
| Bước sai đầu tiên | Bước 3: `model_override` payload: `{"delay_days": 5}` (Ghi đè số ngày giao trễ từ 2 ngày lên 5 ngày theo nội dung ticket, bỏ qua dữ liệu thực tế từ DB). |
| Vì sao là bước đầu tiên | Bước 1 (`handoff`) và Bước 2 (`investigator`) hoàn toàn đúng: tool `lookup_order` tra cứu DB ra chính xác đơn `O-202` có `delay_days: 2` (chưa đủ điều kiện hoàn ship theo chính sách). Sang bước 3, agent bị override thông tin thành 5 ngày dẫn đến bước 4 tính quote sai và bước 6 phát sinh hoàn tiền sai. |
| Failure mode | `FM-03` (ticket_trust — tin lời khai của ticket hơn dữ liệu DB) dẫn tới lỗi kéo theo ở `FM-08` / `FM-04`. |
| Đối chứng | Trên shape `fixed` (cùng `C-002@11`): Không có bước `model_override`. Bước 2 tra cứu DB ra `delay_days: 2` được giữ nguyên sang bước 3 `quote` với `amount_vnd: 0, reason: "no_entitlement"`, và bước 4 trả lời từ chối hoàn tiền hợp lệ (`PASS`). |
| Regression test | Grader `db_fact_kept` / assert kiểm tra không bị ghi đè thông tin từ DB; test kiểm tra `ledger["refund_vnd"] == 0` và `status == "denied"`. |
| Chưa chắc chắn | MockLLM thực hiện override theo rule cố định của variant `seeded_regression`, chưa phản ánh đầy đủ tính bất định (non-deterministic) của LLM thực tế khi gặp prompt injection phức tạp. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
